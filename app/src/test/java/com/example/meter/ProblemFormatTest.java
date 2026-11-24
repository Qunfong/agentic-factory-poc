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
class ProblemFormatTest {

    @Autowired
    MockMvc mvc;

    @Test
    @DisplayName("AC-F34-1: 409 conflict is application/problem+json even with Accept: application/json")
    void ac_f34_1_conflict_is_problem_json_even_with_accept_application_json() throws Exception {
        // First registration succeeds
        mvc.perform(MockMvcRequestBuilders.post("/meters")
                .contentType(MediaType.APPLICATION_JSON)
                .content("{\"id\": \"m1\", \"type\": \"solar\"}"))
            .andExpect(MockMvcResultMatchers.status().isCreated());

        // Second registration conflicts (409) and must be problem+json regardless of Accept header
        mvc.perform(MockMvcRequestBuilders.post("/meters")
                .accept(MediaType.APPLICATION_JSON)
                .contentType(MediaType.APPLICATION_JSON)
                .content("{\"id\": \"m1\", \"type\": \"solar\"}"))
            .andExpect(MockMvcResultMatchers.status().isConflict())
            .andExpect(MockMvcResultMatchers.content().contentTypeCompatibleWith(MediaType.APPLICATION_PROBLEM_JSON))
            .andExpect(MockMvcResultMatchers.jsonPath("$.type").value("/problems/meter-already-registered"))
            .andExpect(MockMvcResultMatchers.jsonPath("$.title").value("Meter already registered"))
            .andExpect(MockMvcResultMatchers.jsonPath("$.status").value(409))
            .andExpect(MockMvcResultMatchers.jsonPath("$.detail").isNotEmpty());
    }

    @Test
    @DisplayName("AC-F34-1: 400 validation error is application/problem+json even with Accept header")
    void ac_f34_1_validation_400_is_problem_json_even_with_accept_header() throws Exception {
        mvc.perform(MockMvcRequestBuilders.post("/meters")
                .accept(MediaType.APPLICATION_JSON)
                .contentType(MediaType.APPLICATION_JSON)
                .content("{\"id\": \"\", \"type\": \"solar\"}"))
            .andExpect(MockMvcResultMatchers.status().isBadRequest())
            .andExpect(MockMvcResultMatchers.content().contentTypeCompatibleWith(MediaType.APPLICATION_PROBLEM_JSON))
            .andExpect(MockMvcResultMatchers.jsonPath("$.type").isNotEmpty())
            .andExpect(MockMvcResultMatchers.jsonPath("$.title").isNotEmpty())
            .andExpect(MockMvcResultMatchers.jsonPath("$.status").value(400))
            .andExpect(MockMvcResultMatchers.jsonPath("$.detail").isNotEmpty());
    }

    @Test
    @DisplayName("AC-F34-5: malformed body on POST /meters returns 400 /problems/malformed-request")
    void ac_f34_5_malformed_body_on_post_meters_returns_400_problem() throws Exception {
        mvc.perform(MockMvcRequestBuilders.post("/meters")
                .contentType(MediaType.APPLICATION_JSON)
                .content("{not json"))
            .andExpect(MockMvcResultMatchers.status().isBadRequest())
            .andExpect(MockMvcResultMatchers.content().contentTypeCompatibleWith(MediaType.APPLICATION_PROBLEM_JSON))
            .andExpect(MockMvcResultMatchers.jsonPath("$.type").value("/problems/malformed-request"))
            .andExpect(MockMvcResultMatchers.jsonPath("$.title").value("Malformed request body"))
            .andExpect(MockMvcResultMatchers.jsonPath("$.status").value(400))
            .andExpect(MockMvcResultMatchers.jsonPath("$.detail").value("The request body is not valid JSON or does not match the expected shape"));
    }

    @Test
    @DisplayName("AC-F34-5: malformed body on POST /readings returns 400 /problems/malformed-request")
    void ac_f34_5_malformed_body_on_post_readings_returns_400_problem() throws Exception {
        mvc.perform(MockMvcRequestBuilders.post("/readings")
                .contentType(MediaType.APPLICATION_JSON)
                .content("{not json"))
            .andExpect(MockMvcResultMatchers.status().isBadRequest())
            .andExpect(MockMvcResultMatchers.content().contentTypeCompatibleWith(MediaType.APPLICATION_PROBLEM_JSON))
            .andExpect(MockMvcResultMatchers.jsonPath("$.type").value("/problems/malformed-request"))
            .andExpect(MockMvcResultMatchers.jsonPath("$.title").value("Malformed request body"))
            .andExpect(MockMvcResultMatchers.jsonPath("$.status").value(400))
            .andExpect(MockMvcResultMatchers.jsonPath("$.detail").value("The request body is not valid JSON or does not match the expected shape"));
    }

    @Test
    @DisplayName("AC-F34-5: wrong JSON type (array) returns 400 /problems/malformed-request on POST /meters")
    void ac_f34_5_wrong_json_type_array_returns_400_problem_on_post_meters() throws Exception {
        mvc.perform(MockMvcRequestBuilders.post("/meters")
                .contentType(MediaType.APPLICATION_JSON)
                .content("[]"))
            .andExpect(MockMvcResultMatchers.status().isBadRequest())
            .andExpect(MockMvcResultMatchers.content().contentTypeCompatibleWith(MediaType.APPLICATION_PROBLEM_JSON))
            .andExpect(MockMvcResultMatchers.jsonPath("$.type").value("/problems/malformed-request"))
            .andExpect(MockMvcResultMatchers.jsonPath("$.title").value("Malformed request body"))
            .andExpect(MockMvcResultMatchers.jsonPath("$.status").value(400))
            .andExpect(MockMvcResultMatchers.jsonPath("$.detail").value("The request body is not valid JSON or does not match the expected shape"));
    }

    @Test
    @DisplayName("AC-F34-5: unknown meter type value uses malformed-request problem")
    void ac_f34_5_unknown_meter_type_uses_malformed_request_problem() throws Exception {
        mvc.perform(MockMvcRequestBuilders.post("/meters")
                .contentType(MediaType.APPLICATION_JSON)
                .content("{\"id\": \"m2\", \"type\": \"unknown\"}"))
            .andExpect(MockMvcResultMatchers.status().isBadRequest())
            .andExpect(MockMvcResultMatchers.content().contentTypeCompatibleWith(MediaType.APPLICATION_PROBLEM_JSON))
            .andExpect(MockMvcResultMatchers.jsonPath("$.type").value("/problems/malformed-request"))
            .andExpect(MockMvcResultMatchers.jsonPath("$.title").value("Malformed request body"))
            .andExpect(MockMvcResultMatchers.jsonPath("$.status").value(400))
            .andExpect(MockMvcResultMatchers.jsonPath("$.detail").value("The request body is not valid JSON or does not match the expected shape"));
    }

    @Test
    @DisplayName("AC-F34-6: unknown paths return 404 /problems/not-found for GET")
    void ac_f34_6_unknown_path_get_returns_404_problem() throws Exception {
        mvc.perform(MockMvcRequestBuilders.get("/nope")
                .accept(MediaType.APPLICATION_JSON))
            .andExpect(MockMvcResultMatchers.status().isNotFound())
            .andExpect(MockMvcResultMatchers.content().contentTypeCompatibleWith(MediaType.APPLICATION_PROBLEM_JSON))
            .andExpect(MockMvcResultMatchers.jsonPath("$.type").value("/problems/not-found"))
            .andExpect(MockMvcResultMatchers.jsonPath("$.title").value("Not Found"))
            .andExpect(MockMvcResultMatchers.jsonPath("$.status").value(404))
            .andExpect(MockMvcResultMatchers.jsonPath("$.detail").value("No endpoint GET /nope"));
    }

    @Test
    @DisplayName("AC-F34-6: unknown paths return 404 /problems/not-found for POST")
    void ac_f34_6_unknown_path_post_returns_404_problem() throws Exception {
        mvc.perform(MockMvcRequestBuilders.post("/readings/abc")
                .contentType(MediaType.APPLICATION_JSON)
                .accept(MediaType.APPLICATION_JSON)
                .content("{}"))
            .andExpect(MockMvcResultMatchers.status().isNotFound())
            .andExpect(MockMvcResultMatchers.content().contentTypeCompatibleWith(MediaType.APPLICATION_PROBLEM_JSON))
            .andExpect(MockMvcResultMatchers.jsonPath("$.type").value("/problems/not-found"))
            .andExpect(MockMvcResultMatchers.jsonPath("$.title").value("Not Found"))
            .andExpect(MockMvcResultMatchers.jsonPath("$.status").value(404))
            .andExpect(MockMvcResultMatchers.jsonPath("$.detail").value("No endpoint POST /readings/abc"));
    }

    @Test
    @DisplayName("AC-F34-6: unknown paths return 404 /problems/not-found for DELETE")
    void ac_f34_6_unknown_path_delete_returns_404_problem() throws Exception {
        mvc.perform(MockMvcRequestBuilders.delete("/meters/x")
                .accept(MediaType.APPLICATION_JSON))
            .andExpect(MockMvcResultMatchers.status().isNotFound())
            .andExpect(MockMvcResultMatchers.content().contentTypeCompatibleWith(MediaType.APPLICATION_PROBLEM_JSON))
            .andExpect(MockMvcResultMatchers.jsonPath("$.type").value("/problems/not-found"))
            .andExpect(MockMvcResultMatchers.jsonPath("$.title").value("Not Found"))
            .andExpect(MockMvcResultMatchers.jsonPath("$.status").value(404))
            .andExpect(MockMvcResultMatchers.jsonPath("$.detail").value("No endpoint DELETE /meters/x"));
    }
}
