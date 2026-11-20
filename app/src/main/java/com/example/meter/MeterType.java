package com.example.meter;

import com.fasterxml.jackson.annotation.JsonCreator;
import com.fasterxml.jackson.annotation.JsonValue;

/** Wire value is the lowercase name; the unit is fixed per type. */
public enum MeterType {
    ELECTRICITY("electricity", "kWh"),
    SOLAR("solar", "kWh"),
    EV_CHARGER("ev_charger", "kWh"),
    GAS("gas", "m3"),
    BATTERY("battery", "kWh"),
    TRANSFORMER("transformer", "kW");

    private final String wire;
    private final String unit;

    MeterType(String wire, String unit) {
        this.wire = wire;
        this.unit = unit;
    }

    @JsonValue
    public String wire() {
        return wire;
    }

    public String unit() {
        return unit;
    }

    /** Exact, case-sensitive match on the wire value; throws UnknownMeterTypeException otherwise. */
    @JsonCreator
    public static MeterType fromWire(String value) {
        for (MeterType type : values()) {
            if (type.wire.equals(value)) {
                return type;
            }
        }
        throw new UnknownMeterTypeException(value);
    }
}
