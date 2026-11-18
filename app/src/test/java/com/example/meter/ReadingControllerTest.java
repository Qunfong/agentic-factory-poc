package com.example.meter;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;

@WebMvcTest(ReadingController.class)
class ReadingControllerTest {
    @Autowired MockMvc mvc;

    @Test
    void rejects_negative_reading() throws Exception {
        mvc.perform(post("/readings").contentType(MediaType.APPLICATION_JSON)
                .content("{\"meterId\":\"m1\",\"takenAt\":\"2026-01-01T00:00:00Z\",\"kwh\":-1}"))
           .andExpect(status().isBadRequest());
    }

    @Test
    void stores_and_lists_reading_per_meter() throws Exception {
        mvc.perform(post("/readings").contentType(MediaType.APPLICATION_JSON)
                .content("{\"meterId\":\"m1\",\"takenAt\":\"2026-01-01T00:00:00Z\",\"kwh\":12.5}"))
           .andExpect(status().isCreated());
        mvc.perform(get("/readings").param("meterId", "m1"))
           .andExpect(status().isOk()).andExpect(jsonPath("$[0].kwh").value(12.5));
    }
}
