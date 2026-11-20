package com.example.meter;

public class UnknownMeterTypeException extends RuntimeException {
    public UnknownMeterTypeException(String value) {
        super("Unknown meter type '" + value + "'");
    }
}
