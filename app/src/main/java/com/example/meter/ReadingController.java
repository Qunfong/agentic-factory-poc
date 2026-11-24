package com.example.meter;

import java.util.List;
import jakarta.validation.Valid;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/readings")
public class ReadingController {

    /** Total number of stored readings; never negative. */
    public record ReadingCount(long count) {}

    private final MeterService service;

    public ReadingController(MeterService service) {
        this.service = service;
    }

    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    public Reading add(@Valid @RequestBody ReadingRequest request) {
        return service.addReading(request);
    }

    @GetMapping
    public List<Reading> list(@RequestParam String meterId) {
        return service.readingsOf(meterId);
    }

    @GetMapping("/count")
    public ReadingCount count() {
        return new ReadingCount(service.readingCount());
    }

    @DeleteMapping
    @ResponseStatus(HttpStatus.NO_CONTENT)
    public void deleteByMeter(@RequestParam String meterId) {
        service.deleteReadingsOf(meterId);
    }
}
