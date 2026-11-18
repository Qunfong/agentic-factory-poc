package com.example.meter;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.List;
import java.util.concurrent.CopyOnWriteArrayList;
import jakarta.validation.Valid;
import jakarta.validation.constraints.DecimalMin;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.*;

/** Seed endpoint so the factory has something real to extend. */
@RestController
@RequestMapping("/readings")
public class ReadingController {

    public record Reading(@NotBlank String meterId, @NotNull Instant takenAt,
                          @NotNull @DecimalMin("0") BigDecimal kwh) {}

    private final List<Reading> readings = new CopyOnWriteArrayList<>();

    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    public Reading add(@Valid @RequestBody Reading reading) {
        readings.add(reading);
        return reading;
    }

    @GetMapping
    public List<Reading> list(@RequestParam String meterId) {
        return readings.stream().filter(r -> r.meterId().equals(meterId)).toList();
    }

    @DeleteMapping
    @ResponseStatus(HttpStatus.NO_CONTENT)
    public void deleteByMeter(@RequestParam String meterId) {
        readings.removeIf(r -> r.meterId().equals(meterId));
    }
}
