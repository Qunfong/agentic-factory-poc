package com.example.meter;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.http.MediaType;
import org.springframework.test.annotation.DirtiesContext;
import org.springframework.test.web.servlet.MockMvc;

@WebMvcTest(ReadingController.class)
@DirtiesContext(classMode = DirtiesContext.ClassMode.BEFORE_EACH_TEST_METHOD)
class ReadingCountTest {
    @Autowired MockMvc mvc;

    @Test
    @DisplayName("AC-F21-1: GET /readings/count returns total count; 0 on fresh context; successful posts increment; rejected post does not")
    void ac_f21_1_returns_count_and_reflects_successful_posts_only() throws Exception {
        // Fresh context: count is 0
        mvc.perform(get("/readings/count"))
           .andExpect(status().isOk())
           .andExpect(jsonPath("$.count").value(0));

        // Post two readings (can be duplicates) -> count rises by 2
        String readingJson = "{\"meterId\":\"m_count_1\",\"takenAt\":\"2026-01-01T00:00:00Z\",\"kwh\":12.5}";
        mvc.perform(post("/readings").contentType(MediaType.APPLICATION_JSON).content(readingJson))
           .andExpect(status().isCreated());
        mvc.perform(post("/readings").contentType(MediaType.APPLICATION_JSON).content(readingJson))
           .andExpect(status().isCreated());

        mvc.perform(get("/readings/count"))
           .andExpect(status().isOk())
           .andExpect(jsonPath("$.count").value(2));

        // Rejected post (negative kwh) does not change count
        String badReading = "{\"meterId\":\"m_count_1\",\"takenAt\":\"2026-01-02T00:00:00Z\",\"kwh\":-1}";
        mvc.perform(post("/readings").contentType(MediaType.APPLICATION_JSON).content(badReading))
           .andExpect(status().isBadRequest());

        mvc.perform(get("/readings/count"))
           .andExpect(status().isOk())
           .andExpect(jsonPath("$.count").value(2));
    }

    @Test
    @DisplayName("AC-F21-2: count reflects deletions per meter; others remain; delete of unknown meter unchanged; posts after delete count again")
    void ac_f21_2_count_reflects_deletions_and_subsequent_posts() throws Exception {
        // Arrange: post readings for two meters: m_del has 2, m_keep has 1
        mvc.perform(post("/readings").contentType(MediaType.APPLICATION_JSON)
                .content("{\"meterId\":\"m_del\",\"takenAt\":\"2026-01-01T00:00:00Z\",\"kwh\":1}"))
           .andExpect(status().isCreated());
        mvc.perform(post("/readings").contentType(MediaType.APPLICATION_JSON)
                .content("{\"meterId\":\"m_del\",\"takenAt\":\"2026-01-02T00:00:00Z\",\"kwh\":2}"))
           .andExpect(status().isCreated());
        mvc.perform(post("/readings").contentType(MediaType.APPLICATION_JSON)
                .content("{\"meterId\":\"m_keep\",\"takenAt\":\"2026-01-03T00:00:00Z\",\"kwh\":3}"))
           .andExpect(status().isCreated());

        // Initial count is 3
        mvc.perform(get("/readings/count"))
           .andExpect(status().isOk())
           .andExpect(jsonPath("$.count").value(3));

        // Delete m_del -> drops by exactly 2
        mvc.perform(delete("/readings").param("meterId", "m_del"))
           .andExpect(status().isNoContent());

        mvc.perform(get("/readings/count"))
           .andExpect(status().isOk())
           .andExpect(jsonPath("$.count").value(1));

        // Deleting unknown meter leaves count unchanged
        mvc.perform(delete("/readings").param("meterId", "unknown"))
           .andExpect(status().isNoContent());
        mvc.perform(get("/readings/count"))
           .andExpect(status().isOk())
           .andExpect(jsonPath("$.count").value(1));

        // Readings posted for the deleted meter after the delete count again
        mvc.perform(post("/readings").contentType(MediaType.APPLICATION_JSON)
                .content("{\"meterId\":\"m_del\",\"takenAt\":\"2026-01-04T00:00:00Z\",\"kwh\":4}"))
           .andExpect(status().isCreated());
        mvc.perform(get("/readings/count"))
           .andExpect(status().isOk())
           .andExpect(jsonPath("$.count").value(2));
    }
}
