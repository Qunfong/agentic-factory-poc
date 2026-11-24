package com.example.meter;

public class MeterNotFoundException extends RuntimeException {
    public MeterNotFoundException(String id) {
        super("Meter '" + id + "' is not registered");
    }
}
