package com.example.meter;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;

@WebMvcTest(ReadingController.class)
class AcF16_1_PostAfterDeleteTest {
    @Autowired MockMvc mvc;

    @Test
    @DisplayName("AC-F16-1: after delete, postings for the same meterId are stored and listed normally")
    void ac_f16_1_allows_post_after_delete() throws Exception {
        // Arrange: post a reading for meter m_reuse_1
        mvc.perform(post("/readings").contentType(MediaType.APPLICATION_JSON)
                .content("{\"meterId\":\"m_reuse_1\",\"takenAt\":\"2026-01-01T00:00:00Z\",\"kwh\":5}"))
           .andExpect(status().isCreated());

        // Act: delete all readings for m_reuse_1
        mvc.perform(delete("/readings").param("meterId", "m_reuse_1"))
           .andExpect(status().isNoContent());

        // Assert: GET m_reuse_1 returns []
        mvc.perform(get("/readings").param("meterId", "m_reuse_1"))
           .andExpect(status().isOk())
           .andExpect(content().json("[]"));

        // Then: post again for the same meter id and ensure it is listed normally
        mvc.perform(post("/readings").contentType(MediaType.APPLICATION_JSON)
                .content("{\"meterId\":\"m_reuse_1\",\"takenAt\":\"2026-01-02T00:00:00Z\",\"kwh\":3.3}"))
           .andExpect(status().isCreated());

        mvc.perform(get("/readings").param("meterId", "m_reuse_1"))
           .andExpect(status().isOk())
           .andExpect(jsonPath("$[0].meterId").value("m_reuse_1"))
           .andExpect(jsonPath("$[0].kwh").value(3.3));
    }
}
