package com.example.meter;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.context.annotation.Import;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.request.MockMvcRequestBuilders;
import org.springframework.test.web.servlet.result.MockMvcResultMatchers;

@WebMvcTest
@Import(MeterService.class)
class FieldValidationProblemTest {

    @Autowired
    MockMvc mvc;

    @Test
    @DisplayName("AC-F34-2: POST /meters with blank id returns 400 validation-failed and names field 'id'")
    void ac_f34_2_blank_id_names_field_on_post_meters() throws Exception {
        mvc.perform(MockMvcRequestBuilders.post("/meters")
                .contentType(MediaType.APPLICATION_JSON)
                .content("{\"id\": \"\", \"type\": \"solar\"}"))
            .andExpect(MockMvcResultMatchers.status().isBadRequest())
            .andExpect(MockMvcResultMatchers.content().contentTypeCompatibleWith(MediaType.APPLICATION_PROBLEM_JSON))
            .andExpect(MockMvcResultMatchers.jsonPath("$.type").value("/problems/validation-failed"))
            .andExpect(MockMvcResultMatchers.jsonPath("$.status").value(400))
            .andExpect(MockMvcResultMatchers.jsonPath("$.errors[0].field").value("id"))
            .andExpect(MockMvcResultMatchers.jsonPath("$.errors[0].message").value(org.hamcrest.Matchers.containsString("must not be blank")))
            .andExpect(MockMvcResultMatchers.jsonPath("$.detail").value(org.hamcrest.Matchers.containsString("id")));
    }

    @Test
    @DisplayName("AC-F34-2: POST /meters with missing id and type lists both fields in errors and detail")
    void ac_f34_2_missing_id_and_type_lists_both_fields() throws Exception {
        mvc.perform(MockMvcRequestBuilders.post("/meters")
                .contentType(MediaType.APPLICATION_JSON)
                .content("{}"))
            .andExpect(MockMvcResultMatchers.status().isBadRequest())
            .andExpect(MockMvcResultMatchers.content().contentTypeCompatibleWith(MediaType.APPLICATION_PROBLEM_JSON))
            .andExpect(MockMvcResultMatchers.jsonPath("$.type").value("/problems/validation-failed"))
            .andExpect(MockMvcResultMatchers.jsonPath("$.status").value(400))
            .andExpect(MockMvcResultMatchers.jsonPath("$.errors[*].field").value(org.hamcrest.Matchers.containsInAnyOrder("id", "type")))
            .andExpect(MockMvcResultMatchers.jsonPath("$.detail").value(org.hamcrest.Matchers.allOf(
                    org.hamcrest.Matchers.containsString("id"),
                    org.hamcrest.Matchers.containsString("type"))));
    }

    @Test
    @DisplayName("AC-F34-3: POST /readings with negative kwh returns 400 validation-failed and names field 'kwh'")
    void ac_f34_3_negative_kwh_names_field_on_post_readings() throws Exception {
        mvc.perform(MockMvcRequestBuilders.post("/readings")
                .contentType(MediaType.APPLICATION_JSON)
                .content("{\"meterId\": \"m1\", \"takenAt\": \"2026-01-01T00:00:00Z\", \"kwh\": -1}"))
            .andExpect(MockMvcResultMatchers.status().isBadRequest())
            .andExpect(MockMvcResultMatchers.content().contentTypeCompatibleWith(MediaType.APPLICATION_PROBLEM_JSON))
            .andExpect(MockMvcResultMatchers.jsonPath("$.type").value("/problems/validation-failed"))
            .andExpect(MockMvcResultMatchers.jsonPath("$.status").value(400))
            .andExpect(MockMvcResultMatchers.jsonPath("$.errors[0].field").value("kwh"))
            .andExpect(MockMvcResultMatchers.jsonPath("$.errors[0].message").value(org.hamcrest.Matchers.containsString("greater than or equal to 0")))
            .andExpect(MockMvcResultMatchers.jsonPath("$.detail").value(org.hamcrest.Matchers.containsString("kwh")));
    }

    @Test
    @DisplayName("AC-F34-3: POST /readings with blank meterId returns 400 validation-failed and names field 'meterId'")
    void ac_f34_3_blank_meter_id_names_field_on_post_readings() throws Exception {
        mvc.perform(MockMvcRequestBuilders.post("/readings")
                .contentType(MediaType.APPLICATION_JSON)
                .content("{\"meterId\": \"\", \"takenAt\": \"2026-01-01T00:00:00Z\", \"kwh\": 1}"))
            .andExpect(MockMvcResultMatchers.status().isBadRequest())
            .andExpect(MockMvcResultMatchers.content().contentTypeCompatibleWith(MediaType.APPLICATION_PROBLEM_JSON))
            .andExpect(MockMvcResultMatchers.jsonPath("$.type").value("/problems/validation-failed"))
            .andExpect(MockMvcResultMatchers.jsonPath("$.status").value(400))
            .andExpect(MockMvcResultMatchers.jsonPath("$.errors[0].field").value("meterId"))
            .andExpect(MockMvcResultMatchers.jsonPath("$.errors[0].message").value(org.hamcrest.Matchers.containsString("must not be blank")))
            .andExpect(MockMvcResultMatchers.jsonPath("$.detail").value(org.hamcrest.Matchers.containsString("meterId")));
    }

    @Test
    @DisplayName("AC-F34-3: POST /readings with missing takenAt returns 400 validation-failed and names field 'takenAt'")
    void ac_f34_3_missing_taken_at_names_field_on_post_readings() throws Exception {
        mvc.perform(MockMvcRequestBuilders.post("/readings")
                .contentType(MediaType.APPLICATION_JSON)
                .content("{\"meterId\": \"m1\", \"kwh\": 1}"))
            .andExpect(MockMvcResultMatchers.status().isBadRequest())
            .andExpect(MockMvcResultMatchers.content().contentTypeCompatibleWith(MediaType.APPLICATION_PROBLEM_JSON))
            .andExpect(MockMvcResultMatchers.jsonPath("$.type").value("/problems/validation-failed"))
            .andExpect(MockMvcResultMatchers.jsonPath("$.status").value(400))
            .andExpect(MockMvcResultMatchers.jsonPath("$.errors[0].field").value("takenAt"))
            .andExpect(MockMvcResultMatchers.jsonPath("$.errors[0].message").value(org.hamcrest.Matchers.containsString("must not be null")))
            .andExpect(MockMvcResultMatchers.jsonPath("$.detail").value(org.hamcrest.Matchers.containsString("takenAt")));
    }

    @Test
    @DisplayName("AC-F34-3: POST /readings with multiple invalid fields lists all offending fields")
    void ac_f34_3_multiple_invalid_fields_listed_on_post_readings() throws Exception {
        mvc.perform(MockMvcRequestBuilders.post("/readings")
                .contentType(MediaType.APPLICATION_JSON)
                .content("{\"meterId\": \"\", \"kwh\": -1}"))
            .andExpect(MockMvcResultMatchers.status().isBadRequest())
            .andExpect(MockMvcResultMatchers.content().contentTypeCompatibleWith(MediaType.APPLICATION_PROBLEM_JSON))
            .andExpect(MockMvcResultMatchers.jsonPath("$.type").value("/problems/validation-failed"))
            .andExpect(MockMvcResultMatchers.jsonPath("$.status").value(400))
            .andExpect(MockMvcResultMatchers.jsonPath("$.errors[*].field").value(org.hamcrest.Matchers.containsInAnyOrder("kwh", "meterId", "takenAt")))
            .andExpect(MockMvcResultMatchers.jsonPath("$.detail").value(org.hamcrest.Matchers.allOf(
                    org.hamcrest.Matchers.containsString("kwh"),
                    org.hamcrest.Matchers.containsString("meterId"),
                    org.hamcrest.Matchers.containsString("takenAt"))));
    }
}
