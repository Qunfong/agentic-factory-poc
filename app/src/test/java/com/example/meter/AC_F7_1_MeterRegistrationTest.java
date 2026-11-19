package com.example.meter;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.context.annotation.Import;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@WebMvcTest(MeterController.class)
@Import(MeterService.class)
class AC_F7_1_MeterRegistrationTest {

    @Autowired MockMvc mvc;
    @Autowired ObjectMapper om;

    // Success cases: registers a meter of each type with correct unit

    @Test
    @DisplayName("AC-F7-1 registers electricity meter with unit kWh")
    void ac_f7_1_registers_electricity_with_unit_kwh() throws Exception {
        mvc.perform(post("/meters")
                .contentType(MediaType.APPLICATION_JSON)
                .content("{\n  \"id\": \"m-elec-1\", \"type\": \"electricity\"\n}"))
            .andExpect(status().isCreated())
            .andExpect(content().contentType(MediaType.APPLICATION_JSON))
            .andExpect(jsonPath("$.id").value("m-elec-1"))
            .andExpect(jsonPath("$.type").value("electricity"))
            .andExpect(jsonPath("$.unit").value("kWh"));
    }

    @Test
    @DisplayName("AC-F7-1 registers solar meter with unit kWh")
    void ac_f7_1_registers_solar_with_unit_kwh() throws Exception {
        mvc.perform(post("/meters")
                .contentType(MediaType.APPLICATION_JSON)
                .content("{\n  \"id\": \"m-solar-1\", \"type\": \"solar\"\n}"))
            .andExpect(status().isCreated())
            .andExpect(content().contentType(MediaType.APPLICATION_JSON))
            .andExpect(jsonPath("$.id").value("m-solar-1"))
            .andExpect(jsonPath("$.type").value("solar"))
            .andExpect(jsonPath("$.unit").value("kWh"));
    }

    @Test
    @DisplayName("AC-F7-1 registers ev_charger meter with unit kWh")
    void ac_f7_1_registers_ev_charger_with_unit_kwh() throws Exception {
        mvc.perform(post("/meters")
                .contentType(MediaType.APPLICATION_JSON)
                .content("{\n  \"id\": \"m-ev-1\", \"type\": \"ev_charger\"\n}"))
            .andExpect(status().isCreated())
            .andExpect(content().contentType(MediaType.APPLICATION_JSON))
            .andExpect(jsonPath("$.id").value("m-ev-1"))
            .andExpect(jsonPath("$.type").value("ev_charger"))
            .andExpect(jsonPath("$.unit").value("kWh"));
    }

    @Test
    @DisplayName("AC-F7-1 registers gas meter with unit m3")
    void ac_f7_1_registers_gas_with_unit_m3() throws Exception {
        mvc.perform(post("/meters")
                .contentType(MediaType.APPLICATION_JSON)
                .content("{\n  \"id\": \"m-gas-1\", \"type\": \"gas\"\n}"))
            .andExpect(status().isCreated())
            .andExpect(content().contentType(MediaType.APPLICATION_JSON))
            .andExpect(jsonPath("$.id").value("m-gas-1"))
            .andExpect(jsonPath("$.type").value("gas"))
            .andExpect(jsonPath("$.unit").value("m3"));
    }

    @Test
    @DisplayName("AC-F7-1 registers battery meter with unit kWh")
    void ac_f7_1_registers_battery_with_unit_kwh() throws Exception {
        mvc.perform(post("/meters")
                .contentType(MediaType.APPLICATION_JSON)
                .content("{\n  \"id\": \"m-batt-1\", \"type\": \"battery\"\n}"))
            .andExpect(status().isCreated())
            .andExpect(content().contentType(MediaType.APPLICATION_JSON))
            .andExpect(jsonPath("$.id").value("m-batt-1"))
            .andExpect(jsonPath("$.type").value("battery"))
            .andExpect(jsonPath("$.unit").value("kWh"));
    }

    @Test
    @DisplayName("AC-F7-1 registers transformer meter with unit kW")
    void ac_f7_1_registers_transformer_with_unit_kw() throws Exception {
        mvc.perform(post("/meters")
                .contentType(MediaType.APPLICATION_JSON)
                .content("{\n  \"id\": \"m-tr-1\", \"type\": \"transformer\"\n}"))
            .andExpect(status().isCreated())
            .andExpect(content().contentType(MediaType.APPLICATION_JSON))
            .andExpect(jsonPath("$.id").value("m-tr-1"))
            .andExpect(jsonPath("$.type").value("transformer"))
            .andExpect(jsonPath("$.unit").value("kW"));
    }

    // Duplicate id -> 409

    @Test
    @DisplayName("AC-F7-1 duplicate id with same type returns 409 and problem type")
    void ac_f7_1_duplicate_id_same_type_409() throws Exception {
        String body = "{\n  \"id\": \"dup-1\", \"type\": \"solar\"\n}";
        mvc.perform(post("/meters").contentType(MediaType.APPLICATION_JSON).content(body))
            .andExpect(status().isCreated());

        mvc.perform(post("/meters").contentType(MediaType.APPLICATION_JSON).content(body))
            .andExpect(status().isConflict())
            .andExpect(content().contentTypeCompatibleWith("application/problem+json"))
            .andExpect(jsonPath("$.type").value("/problems/meter-already-registered"));
    }

    @Test
    @DisplayName("AC-F7-1 duplicate id with different type returns 409 and problem type")
    void ac_f7_1_duplicate_id_different_type_409() throws Exception {
        mvc.perform(post("/meters")
                .contentType(MediaType.APPLICATION_JSON)
                .content("{\n  \"id\": \"dup-2\", \"type\": \"electricity\"\n}"))
            .andExpect(status().isCreated());

        mvc.perform(post("/meters")
                .contentType(MediaType.APPLICATION_JSON)
                .content("{\n  \"id\": \"dup-2\", \"type\": \"gas\"\n}"))
            .andExpect(status().isConflict())
            .andExpect(content().contentTypeCompatibleWith("application/problem+json"))
            .andExpect(jsonPath("$.type").value("/problems/meter-already-registered"));
    }

    // Validation and type parsing errors -> 400

    @Test
    @DisplayName("AC-F7-1 rejects unknown type with 400")
    void ac_f7_1_rejects_unknown_type_400() throws Exception {
        mvc.perform(post("/meters")
                .contentType(MediaType.APPLICATION_JSON)
                .content("{\n  \"id\": \"bad-type-1\", \"type\": \"wind\"\n}"))
            .andExpect(status().isBadRequest());
    }

    @Test
    @DisplayName("AC-F7-1 rejects wrong-case type with 400")
    void ac_f7_1_rejects_wrong_case_type_400() throws Exception {
        mvc.perform(post("/meters")
                .contentType(MediaType.APPLICATION_JSON)
                .content("{\n  \"id\": \"bad-type-2\", \"type\": \"Solar\"\n}"))
            .andExpect(status().isBadRequest());
    }

    @Test
    @DisplayName("AC-F7-1 rejects missing type with 400")
    void ac_f7_1_rejects_missing_type_400() throws Exception {
        mvc.perform(post("/meters")
                .contentType(MediaType.APPLICATION_JSON)
                .content("{\n  \"id\": \"missing-type-1\"\n}"))
            .andExpect(status().isBadRequest());
    }

    @Test
    @DisplayName("AC-F7-1 rejects blank id with 400")
    void ac_f7_1_rejects_blank_id_400() throws Exception {
        mvc.perform(post("/meters")
                .contentType(MediaType.APPLICATION_JSON)
                .content("{\n  \"id\": \"\", \"type\": \"solar\"\n}"))
            .andExpect(status().isBadRequest());
    }

    @Test
    @DisplayName("AC-F7-1 rejects missing id with 400")
    void ac_f7_1_rejects_missing_id_400() throws Exception {
        mvc.perform(post("/meters")
                .contentType(MediaType.APPLICATION_JSON)
                .content("{\n  \"type\": \"solar\"\n}"))
            .andExpect(status().isBadRequest());
    }
}
