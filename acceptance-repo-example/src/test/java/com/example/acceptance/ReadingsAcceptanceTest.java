package com.example.acceptance;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.net.URI;
import java.net.http.*;
import java.util.UUID;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;

class ReadingsAcceptanceTest {
    static final String APP = System.getProperty("app.url", "http://localhost:8080");
    static final HttpClient http = HttpClient.newHttpClient();

    static HttpResponse<String> post(String json) throws Exception {
        var req = HttpRequest.newBuilder(URI.create(APP + "/readings"))
            .header("Content-Type", "application/json")
            .POST(HttpRequest.BodyPublishers.ofString(json))
            .build();
        return http.send(req, HttpResponse.BodyHandlers.ofString());
    }

    static String reading(String meterId, int kwh) {
        return "{\"meterId\":\"" + meterId + "\",\"takenAt\":\"2026-01-01T00:00:00Z\",\"kwh\":" + kwh + "}";
    }

    @Test
    @Tag("AC-F1-1")
    void negative_reading_is_rejected() throws Exception {
        assertEquals(400, post(reading("m-neg", -5)).statusCode());
    }

    @Test
    @Tag("AC-F1-2")
    void valid_reading_is_created() throws Exception {
        assertEquals(201, post(reading("m-new", 5)).statusCode());
    }

    @Test
    @Tag("AC-F1-3")
    void readings_are_listed_per_meter() throws Exception {
        var meter = "m-" + UUID.randomUUID();
        post(reading(meter, 7));
        var req = HttpRequest.newBuilder(URI.create(APP + "/readings?meterId=" + meter)).GET().build();
        var res = http.send(req, HttpResponse.BodyHandlers.ofString());
        assertEquals(200, res.statusCode());
        assertTrue(res.body().contains(meter));
    }

    @Test
    @Tag("AC-F1-4")
    void readings_of_a_meter_can_be_deleted() throws Exception {
        var req = HttpRequest.newBuilder(URI.create(APP + "/readings?meterId=m-new")).DELETE().build();
        assertEquals(204, http.send(req, HttpResponse.BodyHandlers.discarding()).statusCode());
    }
}
