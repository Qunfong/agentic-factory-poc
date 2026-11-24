package com.example.meter;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.context.annotation.Import;
import org.springframework.http.MediaType;
import org.springframework.test.annotation.DirtiesContext;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.request.MockMvcRequestBuilders;
import org.springframework.test.web.servlet.result.MockMvcResultMatchers;

@WebMvcTest
@Import(MeterService.class)
@DirtiesContext(classMode = DirtiesContext.ClassMode.BEFORE_EACH_TEST_METHOD)
class UnregisteredMeterReadingTest {

    @Autowired
    MockMvc mvc;

    @Test
    @DisplayName("AC-F34-4: POST /readings for an unregistered meter returns 404 meter-not-found and stores nothing")
    void ac_f34_4_unregistered_meter_returns_404_and_stores_nothing() throws Exception {
        // Count starts at 0
        mvc.perform(MockMvcRequestBuilders.get("/readings/count"))
           .andExpect(MockMvcResultMatchers.status().isOk())
           .andExpect(MockMvcResultMatchers.jsonPath("$.count").value(0));

        // Post a valid reading for a meter that was never registered -> 404 problem+json
        mvc.perform(MockMvcRequestBuilders.post("/readings")
                .contentType(MediaType.APPLICATION_JSON)
                .content("{\"meterId\": \"unreg-1\", \"takenAt\": \"2026-01-01T00:00:00Z\", \"kwh\": 1}"))
           .andExpect(MockMvcResultMatchers.status().isNotFound())
           .andExpect(MockMvcResultMatchers.content().contentTypeCompatibleWith(MediaType.APPLICATION_PROBLEM_JSON))
           .andExpect(MockMvcResultMatchers.jsonPath("$.type").value("/problems/meter-not-found"))
           .andExpect(MockMvcResultMatchers.jsonPath("$.title").value("Meter not found"))
           .andExpect(MockMvcResultMatchers.jsonPath("$.status").value(404))
           .andExpect(MockMvcResultMatchers.jsonPath("$.detail").value(org.hamcrest.Matchers.containsString("unreg-1")));

        // Count remains 0: nothing stored
        mvc.perform(MockMvcRequestBuilders.get("/readings/count"))
           .andExpect(MockMvcResultMatchers.status().isOk())
           .andExpect(MockMvcResultMatchers.jsonPath("$.count").value(0));
    }

    @Test
    @DisplayName("AC-F34-4: POST /readings for a registered meter still returns 201 and counts")
    void ac_f34_4_registered_meter_returns_201_and_counts() throws Exception {
        // Register meter
        mvc.perform(MockMvcRequestBuilders.post("/meters")
                .contentType(MediaType.APPLICATION_JSON)
                .content("{\"id\": \"m_reg_1\", \"type\": \"solar\"}"))
           .andExpect(MockMvcResultMatchers.status().isCreated());

        // Post a reading for the registered meter -> 201 and count increments
        mvc.perform(MockMvcRequestBuilders.post("/readings")
                .contentType(MediaType.APPLICATION_JSON)
                .content("{\"meterId\": \"m_reg_1\", \"takenAt\": \"2026-01-01T00:00:00Z\", \"kwh\": 5}"))
           .andExpect(MockMvcResultMatchers.status().isCreated());

        mvc.perform(MockMvcRequestBuilders.get("/readings/count"))
           .andExpect(MockMvcResultMatchers.status().isOk())
           .andExpect(MockMvcResultMatchers.jsonPath("$.count").value(1));
    }

    @Test
    @DisplayName("AC-F34-4: validation runs before registry check: negative kwh for unregistered meter is 400 validation-failed")
    void ac_f34_4_negative_kwh_for_unregistered_meter_is_400_validation_failed() throws Exception {
        mvc.perform(MockMvcRequestBuilders.post("/readings")
                .contentType(MediaType.APPLICATION_JSON)
                .content("{\"meterId\": \"unreg-2\", \"takenAt\": \"2026-01-01T00:00:00Z\", \"kwh\": -1}"))
           .andExpect(MockMvcResultMatchers.status().isBadRequest())
           .andExpect(MockMvcResultMatchers.content().contentTypeCompatibleWith(MediaType.APPLICATION_PROBLEM_JSON))
           .andExpect(MockMvcResultMatchers.jsonPath("$.type").value("/problems/validation-failed"))
           .andExpect(MockMvcResultMatchers.jsonPath("$.status").value(400));

        // Count remains 0: rejected post stores nothing
        mvc.perform(MockMvcRequestBuilders.get("/readings/count"))
           .andExpect(MockMvcResultMatchers.status().isOk())
           .andExpect(MockMvcResultMatchers.jsonPath("$.count").value(0));
    }
}
