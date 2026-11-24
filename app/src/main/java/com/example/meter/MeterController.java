package com.example.meter;

import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/meters")
public class MeterController {

    public record RegisterMeterRequest(@NotBlank String id, @NotNull MeterType type) {}

    public record MeterResponse(String id, MeterType type, String unit) {}

    private final MeterService service;

    public MeterController(MeterService service) {
        this.service = service;
    }

    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    public MeterResponse register(@Valid @RequestBody RegisterMeterRequest request) {
        Meter meter = service.register(request.id(), request.type());
        return new MeterResponse(meter.id(), meter.type(), meter.unit());
    }

    @GetMapping("/{id}")
    public MeterResponse get(@PathVariable String id) {
        Meter meter = service.find(id);
        return new MeterResponse(meter.id(), meter.type(), meter.unit());
    }
}
