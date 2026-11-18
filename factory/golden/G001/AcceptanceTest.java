package com.example.meter;

import static org.hamcrest.Matchers.hasSize;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.ResultActions;

@SpringBootTest
@AutoConfigureMockMvc
class AcceptanceTest {

    @Autowired MockMvc mvc;

    @Test
    void ac1_older_reading_returns_409_problem_detail() throws Exception {
        String meter = newMeter();
        postReading(meter, "2026-01-02T00:00:00Z", "10").andExpect(status().isCreated());

        expectConflictProblem(postReading(meter, "2026-01-01T00:00:00Z", "11"));
    }

    @Test
    void ac2_same_taken_at_returns_409() throws Exception {
        String meter = newMeter();
        postReading(meter, "2026-01-02T00:00:00Z", "10").andExpect(status().isCreated());

        expectConflictProblem(postReading(meter, "2026-01-02T00:00:00Z", "11"));
    }

    @Test
    void ac3_meters_do_not_affect_each_other() throws Exception {
        String meterA = newMeter();
        String meterB = newMeter();
        postReading(meterA, "2026-01-02T00:00:00Z", "10").andExpect(status().isCreated());

        postReading(meterB, "2026-01-01T00:00:00Z", "5").andExpect(status().isCreated());
    }

    @Test
    void ac4_newer_reading_is_stored_and_returns_201() throws Exception {
        String meter = newMeter();
        postReading(meter, "2026-01-01T00:00:00Z", "10").andExpect(status().isCreated());
        postReading(meter, "2026-01-02T00:00:00Z", "12").andExpect(status().isCreated());

        mvc.perform(get("/readings").param("meterId", meter))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$", hasSize(2)));
    }

    private static String newMeter() {
        return "m-" + UUID.randomUUID();
    }

    private ResultActions postReading(String meterId, String takenAt, String kwh) throws Exception {
        String body = "{\"meterId\":\"%s\",\"takenAt\":\"%s\",\"kwh\":%s}".formatted(meterId, takenAt, kwh);
        return mvc.perform(post("/readings").contentType(MediaType.APPLICATION_JSON).content(body));
    }

    private static void expectConflictProblem(ResultActions result) throws Exception {
        result.andExpect(status().isConflict())
                .andExpect(content().contentTypeCompatibleWith(MediaType.APPLICATION_PROBLEM_JSON))
                .andExpect(jsonPath("$.status").value(409));
    }
}
