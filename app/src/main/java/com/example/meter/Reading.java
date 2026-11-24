package com.example.meter;

import java.math.BigDecimal;
import java.time.Instant;

/** Stored reading; type and unit are stamped by the server from the registered meter. */
public record Reading(String meterId, Instant takenAt, BigDecimal quantity,
                      MeterType type, String unit) {}
