package com.example.meter;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.context.annotation.Import;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@WebMvcTest(MeterController.class)
@Import(MeterService.class)
class MeterLookupTest {

    @Autowired MockMvc mvc;

    // AC-F32-1: returns the registered meter (id, type, unit) for each type

    @Test
    @DisplayName("AC-F32-1 returns electricity meter with unit kWh")
    void ac_f32_1_returns_electricity_with_unit_kwh() throws Exception {
        mvc.perform(post("/meters").contentType(MediaType.APPLICATION_JSON)
                .content("{\n  \"id\": \"m-elec-get-1\", \"type\": \"electricity\"\n}"))
            .andExpect(status().isCreated());

        mvc.perform(get("/meters/m-elec-get-1"))
            .andExpect(status().isOk())
            .andExpect(content().contentType(MediaType.APPLICATION_JSON))
            .andExpect(jsonPath("$.id").value("m-elec-get-1"))
            .andExpect(jsonPath("$.type").value("electricity"))
            .andExpect(jsonPath("$.unit").value("kWh"));
    }

    @Test
    @DisplayName("AC-F32-1 returns solar meter with unit kWh")
    void ac_f32_1_returns_solar_with_unit_kwh() throws Exception {
        mvc.perform(post("/meters").contentType(MediaType.APPLICATION_JSON)
                .content("{\n  \"id\": \"m-solar-get-1\", \"type\": \"solar\"\n}"))
            .andExpect(status().isCreated());

        mvc.perform(get("/meters/m-solar-get-1"))
            .andExpect(status().isOk())
            .andExpect(content().contentType(MediaType.APPLICATION_JSON))
            .andExpect(jsonPath("$.id").value("m-solar-get-1"))
            .andExpect(jsonPath("$.type").value("solar"))
            .andExpect(jsonPath("$.unit").value("kWh"));
    }

    @Test
    @DisplayName("AC-F32-1 returns ev_charger meter with unit kWh")
    void ac_f32_1_returns_ev_charger_with_unit_kwh() throws Exception {
        mvc.perform(post("/meters").contentType(MediaType.APPLICATION_JSON)
                .content("{\n  \"id\": \"m-ev-get-1\", \"type\": \"ev_charger\"\n}"))
            .andExpect(status().isCreated());

        mvc.perform(get("/meters/m-ev-get-1"))
            .andExpect(status().isOk())
            .andExpect(content().contentType(MediaType.APPLICATION_JSON))
            .andExpect(jsonPath("$.id").value("m-ev-get-1"))
            .andExpect(jsonPath("$.type").value("ev_charger"))
            .andExpect(jsonPath("$.unit").value("kWh"));
    }

    @Test
    @DisplayName("AC-F32-1 returns gas meter with unit m3")
    void ac_f32_1_returns_gas_with_unit_m3() throws Exception {
        mvc.perform(post("/meters").contentType(MediaType.APPLICATION_JSON)
                .content("{\n  \"id\": \"m-gas-get-1\", \"type\": \"gas\"\n}"))
            .andExpect(status().isCreated());

        mvc.perform(get("/meters/m-gas-get-1"))
            .andExpect(status().isOk())
            .andExpect(content().contentType(MediaType.APPLICATION_JSON))
            .andExpect(jsonPath("$.id").value("m-gas-get-1"))
            .andExpect(jsonPath("$.type").value("gas"))
            .andExpect(jsonPath("$.unit").value("m3"));
    }

    @Test
    @DisplayName("AC-F32-1 returns battery meter with unit kWh")
    void ac_f32_1_returns_battery_with_unit_kwh() throws Exception {
        mvc.perform(post("/meters").contentType(MediaType.APPLICATION_JSON)
                .content("{\n  \"id\": \"m-batt-get-1\", \"type\": \"battery\"\n}"))
            .andExpect(status().isCreated());

        mvc.perform(get("/meters/m-batt-get-1"))
            .andExpect(status().isOk())
            .andExpect(content().contentType(MediaType.APPLICATION_JSON))
            .andExpect(jsonPath("$.id").value("m-batt-get-1"))
            .andExpect(jsonPath("$.type").value("battery"))
            .andExpect(jsonPath("$.unit").value("kWh"));
    }

    @Test
    @DisplayName("AC-F32-1 returns transformer meter with unit kW")
    void ac_f32_1_returns_transformer_with_unit_kw() throws Exception {
        mvc.perform(post("/meters").contentType(MediaType.APPLICATION_JSON)
                .content("{\n  \"id\": \"m-tr-get-1\", \"type\": \"transformer\"\n}"))
            .andExpect(status().isCreated());

        mvc.perform(get("/meters/m-tr-get-1"))
            .andExpect(status().isOk())
            .andExpect(content().contentType(MediaType.APPLICATION_JSON))
            .andExpect(jsonPath("$.id").value("m-tr-get-1"))
            .andExpect(jsonPath("$.type").value("transformer"))
            .andExpect(jsonPath("$.unit").value("kW"));
    }

    @Test
    @DisplayName("AC-F32-1 returns only the requested meter among several")
    void ac_f32_1_returns_only_requested_meter_among_several() throws Exception {
        // Register several meters
        mvc.perform(post("/meters").contentType(MediaType.APPLICATION_JSON)
                .content("{\n  \"id\": \"m-one\", \"type\": \"electricity\"\n}"))
            .andExpect(status().isCreated());
        mvc.perform(post("/meters").contentType(MediaType.APPLICATION_JSON)
                .content("{\n  \"id\": \"m-two\", \"type\": \"gas\"\n}"))
            .andExpect(status().isCreated());
        mvc.perform(post("/meters").contentType(MediaType.APPLICATION_JSON)
                .content("{\n  \"id\": \"m-three\", \"type\": \"battery\"\n}"))
            .andExpect(status().isCreated());

        // Lookup one of them
        mvc.perform(get("/meters/m-two"))
            .andExpect(status().isOk())
            .andExpect(content().contentType(MediaType.APPLICATION_JSON))
            .andExpect(jsonPath("$.id").value("m-two"))
            .andExpect(jsonPath("$.type").value("gas"))
            .andExpect(jsonPath("$.unit").value("m3"));
    }

    @Test
    @DisplayName("AC-F32-1 repeated GET returns the same body and changes nothing")
    void ac_f32_1_repeated_get_is_idempotent() throws Exception {
        mvc.perform(post("/meters").contentType(MediaType.APPLICATION_JSON)
                .content("{\n  \"id\": \"m-repeat\", \"type\": \"solar\"\n}"))
            .andExpect(status().isCreated());

        mvc.perform(get("/meters/m-repeat"))
            .andExpect(status().isOk())
            .andExpect(content().contentType(MediaType.APPLICATION_JSON))
            .andExpect(jsonPath("$.id").value("m-repeat"))
            .andExpect(jsonPath("$.type").value("solar"))
            .andExpect(jsonPath("$.unit").value("kWh"));

        mvc.perform(get("/meters/m-repeat"))
            .andExpect(status().isOk())
            .andExpect(content().contentType(MediaType.APPLICATION_JSON))
            .andExpect(jsonPath("$.id").value("m-repeat"))
            .andExpect(jsonPath("$.type").value("solar"))
            .andExpect(jsonPath("$.unit").value("kWh"));
    }

    // AC-F32-2: 404 problem+json when id not found

    @Test
    @DisplayName("AC-F32-2 unknown id returns 404 problem with type and title and detail naming the id")
    void ac_f32_2_unknown_id_404_problem() throws Exception {
        mvc.perform(get("/meters/never-registered-1"))
            .andExpect(status().isNotFound())
            .andExpect(content().contentTypeCompatibleWith("application/problem+json"))
            .andExpect(jsonPath("$.type").value("/problems/meter-not-found"))
            .andExpect(jsonPath("$.title").value("Meter not found"))
            .andExpect(jsonPath("$.detail").value("Meter 'never-registered-1' is not registered"));
    }

    @Test
    @DisplayName("AC-F32-2 case-sensitive id miss returns 404 problem")
    void ac_f32_2_case_sensitive_id_miss_404() throws Exception {
        mvc.perform(post("/meters").contentType(MediaType.APPLICATION_JSON)
                .content("{\n  \"id\": \"m-case-1\", \"type\": \"battery\"\n}"))
            .andExpect(status().isCreated());

        mvc.perform(get("/meters/M-case-1"))
            .andExpect(status().isNotFound())
            .andExpect(content().contentTypeCompatibleWith("application/problem+json"))
            .andExpect(jsonPath("$.type").value("/problems/meter-not-found"))
            .andExpect(jsonPath("$.title").value("Meter not found"))
            .andExpect(jsonPath("$.detail").value("Meter 'M-case-1' is not registered"));
    }

    @Test
    @DisplayName("AC-F32-2 failed registration does not make id findable")
    void ac_f32_2_failed_registration_still_404() throws Exception {
        // Attempt a registration that fails with 400 due to unknown type
        mvc.perform(post("/meters").contentType(MediaType.APPLICATION_JSON)
                .content("{\n  \"id\": \"bad-type-lookup-1\", \"type\": \"wind\"\n}"))
            .andExpect(status().isBadRequest());

        // Lookup returns 404 problem
        mvc.perform(get("/meters/bad-type-lookup-1"))
            .andExpect(status().isNotFound())
            .andExpect(content().contentTypeCompatibleWith("application/problem+json"))
            .andExpect(jsonPath("$.type").value("/problems/meter-not-found"))
            .andExpect(jsonPath("$.title").value("Meter not found"))
            .andExpect(jsonPath("$.detail").value("Meter 'bad-type-lookup-1' is not registered"));
    }
}
