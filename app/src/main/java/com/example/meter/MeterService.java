package com.example.meter;

import java.util.List;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ConcurrentMap;
import java.util.concurrent.CopyOnWriteArrayList;
import org.springframework.stereotype.Service;

@Service
public class MeterService {

    private final ConcurrentMap<String, Meter> meters = new ConcurrentHashMap<>();
    private final List<Reading> readings = new CopyOnWriteArrayList<>();

    /** Atomic putIfAbsent; throws MeterAlreadyRegisteredException if the id exists. */
    public Meter register(String id, MeterType type) {
        Meter meter = new Meter(id, type);
        if (meters.putIfAbsent(id, meter) != null) {
            throw new MeterAlreadyRegisteredException(id);
        }
        return meter;
    }

    /** Throws MeterNotFoundException if the meter is not registered. */
    public Reading addReading(ReadingRequest request) {
        Meter meter = meters.get(request.meterId());
        if (meter == null) {
            throw new MeterNotFoundException(request.meterId());
        }
        Reading reading = new Reading(meter.id(), request.takenAt(), request.quantity(),
                meter.type(), meter.unit());
        readings.add(reading);
        return reading;
    }

    public List<Reading> readingsOf(String meterId) {
        return readings.stream().filter(r -> r.meterId().equals(meterId)).toList();
    }

    public long readingCount() {
        return readings.size();
    }

    /** removeIf on meterId; registration of the meter stays. */
    public void deleteReadingsOf(String meterId) {
        readings.removeIf(r -> r.meterId().equals(meterId));
    }
}
