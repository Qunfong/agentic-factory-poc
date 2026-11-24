package com.example.meter;

import com.fasterxml.jackson.annotation.JsonAlias;
import jakarta.validation.constraints.DecimalMin;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import java.math.BigDecimal;
import java.time.Instant;

/** POST /readings body; the client sends no type or unit. */
public record ReadingRequest(@NotBlank String meterId, @NotNull Instant takenAt,
                             @NotNull @DecimalMin("0") @JsonAlias("kwh") BigDecimal quantity) {}
