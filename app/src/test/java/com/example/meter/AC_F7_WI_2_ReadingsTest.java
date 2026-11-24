package com.example.meter;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.context.annotation.Import;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.delete;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * F7 WI-2: Readings only for registered meters, carrying the meter type and unit; delete unchanged
 * Covers AC-F7-2, AC-F7-3, AC-F7-4, AC-F7-7 via the HTTP public interface.
 */
@WebMvcTest({ReadingController.class, MeterController.class})
@Import(MeterService.class)
class AC_F7_WI_2_ReadingsTest {

    @Autowired MockMvc mvc;
    @Autowired ObjectMapper om;

    // AC-F7-2: POST /readings for an unregistered meter returns 404 and problem type

    @Test
    @DisplayName("AC-F7-2 unregistered meter returns 404 and problem type")
    void ac_f7_2_unregistered_meter_returns_404_and_problem_type() throws Exception {
        mvc.perform(post("/readings")
                .contentType(MediaType.APPLICATION_JSON)
                .content("{\n  \"meterId\": \"unreg-1\", \"takenAt\": \"2026-01-01T00:00:00Z\", \"quantity\": 1.0\n}"))
            .andExpect(status().isNotFound())
            .andExpect(content().contentTypeCompatibleWith("application/problem+json"))
            .andExpect(jsonPath("$.type").value("/problems/meter-not-found"));
    }

    @Test
    @DisplayName("AC-F7-2 negative quantity returns 400 before 404")
    void ac_f7_2_negative_quantity_returns_400_before_404() throws Exception {
        mvc.perform(post("/readings")
                .contentType(MediaType.APPLICATION_JSON)
                .content("{\n  \"meterId\": \"unreg-2\", \"takenAt\": \"2026-01-01T00:00:00Z\", \"quantity\": -1.0\n}"))
            .andExpect(status().isBadRequest());
    }

    // AC-F7-3: unit stamping and quantity alias

    @Test
    @DisplayName("AC-F7-3 POST response includes type and unit for kWh type (solar)")
    void ac_f7_3_post_response_includes_type_and_unit_for_kwh_type() throws Exception {
        // Register a solar meter
        mvc.perform(post("/meters")
                .contentType(MediaType.APPLICATION_JSON)
                .content("{\n  \"id\": \"pv-100\", \"type\": \"solar\"\n}"))
            .andExpect(status().isCreated());

        // Post a reading against it
        mvc.perform(post("/readings")
                .contentType(MediaType.APPLICATION_JSON)
                .content("{\n  \"meterId\": \"pv-100\", \"takenAt\": \"2026-01-01T00:00:00Z\", \"quantity\": 12.5\n}"))
            .andExpect(status().isCreated())
            .andExpect(content().contentType(MediaType.APPLICATION_JSON))
            .andExpect(jsonPath("$.meterId").value("pv-100"))
            .andExpect(jsonPath("$.takenAt").value("2026-01-01T00:00:00Z"))
            .andExpect(jsonPath("$.quantity").value(12.5))
            .andExpect(jsonPath("$.type").value("solar"))
            .andExpect(jsonPath("$.unit").value("kWh"));
    }

    @Test
    @DisplayName("AC-F7-3 POST accepts kwh as input alias and stamps unit")
    void ac_f7_3_post_accepts_kwh_input_alias_and_stamps_unit() throws Exception {
        // Register an EV charger meter
        mvc.perform(post("/meters")
                .contentType(MediaType.APPLICATION_JSON)
                .content("{\n  \"id\": \"ev-100\", \"type\": \"ev_charger\"\n}"))
            .andExpect(status().isCreated());

        // Post a reading with kwh alias
        mvc.perform(post("/readings")
                .contentType(MediaType.APPLICATION_JSON)
                .content("{\n  \"meterId\": \"ev-100\", \"takenAt\": \"2026-01-01T00:00:00Z\", \"kwh\": 3.2\n}"))
            .andExpect(status().isCreated())
            .andExpect(content().contentType(MediaType.APPLICATION_JSON))
            .andExpect(jsonPath("$.meterId").value("ev-100"))
            .andExpect(jsonPath("$.quantity").value(3.2))
            .andExpect(jsonPath("$.type").value("ev_charger"))
            .andExpect(jsonPath("$.unit").value("kWh"));
    }

    @Test
    @DisplayName("AC-F7-3 negative quantity rejected with 400 for gas meter")
    void ac_f7_3_negative_quantity_rejected_with_400_for_gas_meter() throws Exception {
        // Register a gas meter
        mvc.perform(post("/meters")
                .contentType(MediaType.APPLICATION_JSON)
                .content("{\n  \"id\": \"gas-100\", \"type\": \"gas\"\n}"))
            .andExpect(status().isCreated());

        // Post a negative reading against it
        mvc.perform(post("/readings")
                .contentType(MediaType.APPLICATION_JSON)
                .content("{\n  \"meterId\": \"gas-100\", \"takenAt\": \"2026-01-01T00:00:00Z\", \"quantity\": -0.1\n}"))
            .andExpect(status().isBadRequest());
    }

    // AC-F7-4: GET /readings includes type and unit; empty list for id with no readings

    @Test
    @DisplayName("AC-F7-4 GET list includes type and unit for each reading")
    void ac_f7_4_get_list_includes_type_and_unit_for_each_reading() throws Exception {
        // Register a transformer meter (unit kW)
        mvc.perform(post("/meters")
                .contentType(MediaType.APPLICATION_JSON)
                .content("{\n  \"id\": \"tr-100\", \"type\": \"transformer\"\n}"))
            .andExpect(status().isCreated());

        // Post two readings
        mvc.perform(post("/readings")
                .contentType(MediaType.APPLICATION_JSON)
                .content("{\n  \"meterId\": \"tr-100\", \"takenAt\": \"2026-02-01T00:00:00Z\", \"quantity\": 1.0\n}"))
            .andExpect(status().isCreated());
        mvc.perform(post("/readings")
                .contentType(MediaType.APPLICATION_JSON)
                .content("{\n  \"meterId\": \"tr-100\", \"takenAt\": \"2026-02-02T00:00:00Z\", \"quantity\": 2.5\n}"))
            .andExpect(status().isCreated());

        // List readings and check type and unit are included
        mvc.perform(get("/readings").param("meterId", "tr-100"))
            .andExpect(status().isOk())
            .andExpect(content().contentType(MediaType.APPLICATION_JSON))
            .andExpect(jsonPath("$[0].meterId").value("tr-100"))
            .andExpect(jsonPath("$[0].type").value("transformer"))
            .andExpect(jsonPath("$[0].unit").value("kW"))
            .andExpect(jsonPath("$[1].meterId").value("tr-100"))
            .andExpect(jsonPath("$[1].type").value("transformer"))
            .andExpect(jsonPath("$[1].unit").value("kW"));
    }

    @Test
    @DisplayName("AC-F7-4 GET list returns empty array for id with no readings (unregistered or none)")
    void ac_f7_4_get_list_returns_empty_array_for_unregistered_meter() throws Exception {
        mvc.perform(get("/readings").param("meterId", "unknown-200"))
            .andExpect(status().isOk())
            .andExpect(content().json("[]"));
    }

    // AC-F7-7: DELETE /readings is unchanged: removes only its meter's readings, returns 204, keeps registration

    @Test
    @DisplayName("AC-F7-7 delete removes only target meter readings")
    void ac_f7_7_delete_removes_only_target_meter_readings() throws Exception {
        // Register two meters of different types
        mvc.perform(post("/meters")
                .contentType(MediaType.APPLICATION_JSON)
                .content("{\n  \"id\": \"elec-del-1\", \"type\": \"electricity\"\n}"))
            .andExpect(status().isCreated());
        mvc.perform(post("/meters")
                .contentType(MediaType.APPLICATION_JSON)
                .content("{\n  \"id\": \"solar-del-1\", \"type\": \"solar\"\n}"))
            .andExpect(status().isCreated());

        // Post one reading each
        mvc.perform(post("/readings")
                .contentType(MediaType.APPLICATION_JSON)
                .content("{\n  \"meterId\": \"elec-del-1\", \"takenAt\": \"2026-03-01T00:00:00Z\", \"quantity\": 5\n}"))
            .andExpect(status().isCreated());
        mvc.perform(post("/readings")
                .contentType(MediaType.APPLICATION_JSON)
                .content("{\n  \"meterId\": \"solar-del-1\", \"takenAt\": \"2026-03-01T01:00:00Z\", \"quantity\": 7\n}"))
            .andExpect(status().isCreated());

        // Delete readings of electricity meter
        mvc.perform(delete("/readings").param("meterId", "elec-del-1"))
            .andExpect(status().isNoContent());

        // Electricity readings removed
        mvc.perform(get("/readings").param("meterId", "elec-del-1"))
            .andExpect(status().isOk())
            .andExpect(content().json("[]"));

        // Solar readings remain
        mvc.perform(get("/readings").param("meterId", "solar-del-1"))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$[0].meterId").value("solar-del-1"));
    }

    @Test
    @DisplayName("AC-F7-7 delete on unregistered id returns 204 with no body")
    void ac_f7_7_delete_unregistered_id_returns_204_no_body() throws Exception {
        mvc.perform(delete("/readings").param("meterId", "not_reg_del_1"))
            .andExpect(status().isNoContent())
            .andExpect(content().string(""));
    }

    @Test
    @DisplayName("AC-F7-7 delete without meterId returns 400")
    void ac_f7_7_delete_without_meterId_returns_400() throws Exception {
        mvc.perform(delete("/readings"))
            .andExpect(status().isBadRequest());
    }

    @Test
    @DisplayName("AC-F7-7 delete does not unregister meter; new readings carry same type and unit")
    void ac_f7_7_delete_does_not_unregister_meter_and_new_readings_carry_type_unit() throws Exception {
        // Register battery meter
        mvc.perform(post("/meters")
                .contentType(MediaType.APPLICATION_JSON)
                .content("{\n  \"id\": \"batt-del-1\", \"type\": \"battery\"\n}"))
            .andExpect(status().isCreated());

        // Post a reading
        mvc.perform(post("/readings")
                .contentType(MediaType.APPLICATION_JSON)
                .content("{\n  \"meterId\": \"batt-del-1\", \"takenAt\": \"2026-04-01T00:00:00Z\", \"quantity\": 1.5\n}"))
            .andExpect(status().isCreated());

        // Delete all readings of the meter
        mvc.perform(delete("/readings").param("meterId", "batt-del-1"))
            .andExpect(status().isNoContent());

        // Post a new reading after delete; it should be accepted and carry the same type and unit
        mvc.perform(post("/readings")
                .contentType(MediaType.APPLICATION_JSON)
                .content("{\n  \"meterId\": \"batt-del-1\", \"takenAt\": \"2026-04-02T00:00:00Z\", \"quantity\": 2.0\n}"))
            .andExpect(status().isCreated())
            .andExpect(jsonPath("$.type").value("battery"))
            .andExpect(jsonPath("$.unit").value("kWh"));
    }
}
