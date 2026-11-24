package com.example.meter;

import java.math.BigDecimal;
import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.util.Comparator;
import java.util.List;
import java.util.concurrent.CopyOnWriteArrayList;
import jakarta.validation.Valid;
import jakarta.validation.constraints.DecimalMin;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

/** Seed endpoint so the factory has something real to extend. */
@RestController
@RequestMapping("/readings")
public class ReadingController {

    public record Reading(@NotBlank String meterId, @NotNull Instant takenAt,
                          @NotNull @DecimalMin("0") BigDecimal kwh) {}

    /** Total number of stored readings; never negative. */
    public record ReadingCount(long count) {}

    static final String CSV_HEADER = "meterId,timestamp,value";
    // explicit UTF-8: StringHttpMessageConverter would otherwise default to ISO-8859-1
    static final MediaType TEXT_CSV_UTF8 = new MediaType("text", "csv", StandardCharsets.UTF_8);

    private final List<Reading> readings = new CopyOnWriteArrayList<>();

    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    public Reading add(@Valid @RequestBody Reading reading) {
        readings.add(reading);
        return reading;
    }

    @GetMapping
    public List<Reading> list(@RequestParam(required = false) String meterId,
                              @RequestParam(required = false) Instant from,
                              @RequestParam(required = false) Instant to,
                              @RequestParam(defaultValue = "0") @Min(0) int page,
                              @RequestParam(defaultValue = "20") @Min(1) @Max(100) int size) {
        // Stream.sorted is stable on an ordered stream, so equal takenAt keep insertion order.
        return readings.stream()
                .filter(r -> meterId == null || r.meterId().equals(meterId))
                .filter(r -> from == null || !r.takenAt().isBefore(from))
                .filter(r -> to == null || !r.takenAt().isAfter(to))
                .sorted(Comparator.comparing(Reading::takenAt))
                .skip((long) page * size)
                .limit(size)
                .toList();
    }

    @GetMapping("/count")
    public ReadingCount count() {
        return new ReadingCount(readings.size());
    }

    @GetMapping("/export")
    public ResponseEntity<String> export() {
        StringBuilder csv = new StringBuilder(CSV_HEADER).append("\r\n");
        for (Reading r : readings) { // snapshot iterator: consistent under concurrent writes
            csv.append(csvField(r.meterId())).append(',')
               .append(csvField(r.takenAt().toString())).append(',')
               .append(csvField(r.kwh().toPlainString())).append("\r\n");
        }
        return ResponseEntity.ok().contentType(TEXT_CSV_UTF8).body(csv.toString());
    }

    /** RFC 4180 field: quoted iff it contains ',', '"', CR or LF; inner '"' doubled. */
    static String csvField(String raw) {
        if (raw.indexOf(',') < 0 && raw.indexOf('"') < 0 && raw.indexOf('\r') < 0 && raw.indexOf('\n') < 0) {
            return raw;
        }
        return '"' + raw.replace("\"", "\"\"") + '"';
    }

    @DeleteMapping
    @ResponseStatus(HttpStatus.NO_CONTENT)
    public void deleteByMeter(@RequestParam String meterId) {
        readings.removeIf(r -> r.meterId().equals(meterId));
    }
}
