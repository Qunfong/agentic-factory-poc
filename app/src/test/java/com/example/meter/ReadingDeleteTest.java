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
class ReadingDeleteTest {
    @Autowired MockMvc mvc;

    @Test
    @DisplayName("AC-F16-1: delete removes all readings for the meter and returns 204; others remain")
    void ac_f16_1_deletes_readings_for_meter_and_leaves_others() throws Exception {
        // Arrange: post one reading for m_del and one for m_keep
        mvc.perform(post("/readings").contentType(MediaType.APPLICATION_JSON)
                .content("{\"meterId\":\"m_del_1\",\"takenAt\":\"2026-01-01T00:00:00Z\",\"kwh\":12.5}"))
           .andExpect(status().isCreated());
        mvc.perform(post("/readings").contentType(MediaType.APPLICATION_JSON)
                .content("{\"meterId\":\"m_keep_1\",\"takenAt\":\"2026-01-02T00:00:00Z\",\"kwh\":7.0}"))
           .andExpect(status().isCreated());

        // Act: delete readings for m_del_1
        mvc.perform(delete("/readings").param("meterId", "m_del_1"))
           .andExpect(status().isNoContent());

        // Assert: GET m_del_1 returns []
        mvc.perform(get("/readings").param("meterId", "m_del_1"))
           .andExpect(status().isOk())
           .andExpect(content().json("[]"));
        // Assert: GET m_keep_1 still lists its reading
        mvc.perform(get("/readings").param("meterId", "m_keep_1"))
           .andExpect(status().isOk())
           .andExpect(jsonPath("$[0].meterId").value("m_keep_1"));
    }

    @Test
    @DisplayName("AC-F16-1: delete on meter with no readings returns 204")
    void ac_f16_1_delete_unknown_meter_returns_204() throws Exception {
        mvc.perform(delete("/readings").param("meterId", "never_seen_1"))
           .andExpect(status().isNoContent());
    }

    @Test
    @DisplayName("AC-F16-1: delete is idempotent; repeated call returns 204")
    void ac_f16_1_delete_is_idempotent() throws Exception {
        // Arrange: create one reading then delete it
        mvc.perform(post("/readings").contentType(MediaType.APPLICATION_JSON)
                .content("{\"meterId\":\"m_idem_1\",\"takenAt\":\"2026-01-03T00:00:00Z\",\"kwh\":1}"))
           .andExpect(status().isCreated());

        mvc.perform(delete("/readings").param("meterId", "m_idem_1"))
           .andExpect(status().isNoContent());
        // Repeat delete: still 204
        mvc.perform(delete("/readings").param("meterId", "m_idem_1"))
           .andExpect(status().isNoContent());
    }

    @Test
    @DisplayName("AC-F16-1: missing meterId parameter yields 400 Bad Request")
    void ac_f16_1_missing_meter_id_returns_400() throws Exception {
        mvc.perform(delete("/readings"))
           .andExpect(status().isBadRequest());
    }
}
