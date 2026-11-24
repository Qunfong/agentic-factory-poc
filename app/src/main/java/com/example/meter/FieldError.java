package com.example.meter;

/** One offending input; extension property "errors" on validation problems (ADR proposed-problem-field-errors). */
public record FieldError(String field, String message) {}
