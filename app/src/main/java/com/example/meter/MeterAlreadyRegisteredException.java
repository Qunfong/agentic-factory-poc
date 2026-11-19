package com.example.meter;

public class MeterAlreadyRegisteredException extends RuntimeException {
    public MeterAlreadyRegisteredException(String id) {
        super("Meter '" + id + "' is already registered");
    }
}
