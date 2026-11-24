package com.example.meter;

import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ConcurrentMap;
import org.springframework.stereotype.Service;

@Service
public class MeterService {

    private final ConcurrentMap<String, Meter> meters = new ConcurrentHashMap<>();

    /** Atomic putIfAbsent; throws MeterAlreadyRegisteredException if the id exists. */
    public Meter register(String id, MeterType type) {
        Meter meter = new Meter(id, type);
        if (meters.putIfAbsent(id, meter) != null) {
            throw new MeterAlreadyRegisteredException(id);
        }
        return meter;
    }

    /** Returns the registered meter; throws MeterNotFoundException if no meter has this id. */
    public Meter find(String id) {
        Meter meter = meters.get(id);
        if (meter == null) {
            throw new MeterNotFoundException(id);
        }
        return meter;
    }
}
