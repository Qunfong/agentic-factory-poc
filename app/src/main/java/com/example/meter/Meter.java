package com.example.meter;

public record Meter(String id, MeterType type) {
    public String unit() {
        return type.unit();
    }
}
