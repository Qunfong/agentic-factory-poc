package com.example.meter;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

import java.nio.charset.StandardCharsets;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.test.annotation.DirtiesContext;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.MvcResult;

@WebMvcTest(ReadingController.class)
@DirtiesContext(classMode = DirtiesContext.ClassMode.BEFORE_EACH_TEST_METHOD)
class ReadingExportTest {
    @Autowired MockMvc mvc;

    @Test
    @DisplayName("AC-F36-1: GET /readings/export returns 200, Content-Type compatible with text/csv; first line is exactly meterId,timestamp,value followed by CRLF")
    void ac_f36_1_header_and_content_type() throws Exception {
        MvcResult res = mvc.perform(get("/readings/export"))
            .andExpect(status().isOk())
            .andExpect(content().contentTypeCompatibleWith("text/csv"))
            .andReturn();

        String body = res.getResponse().getContentAsString(StandardCharsets.UTF_8);
        assertThat(body).startsWith("meterId,timestamp,value\r\n");
    }

    @Test
    @DisplayName("AC-F36-2: With no readings stored, body is only the header line with CRLF")
    void ac_f36_2_header_only_when_empty() throws Exception {
        MvcResult res = mvc.perform(get("/readings/export"))
            .andExpect(status().isOk())
            .andExpect(content().contentTypeCompatibleWith("text/csv"))
            .andReturn();

        String body = res.getResponse().getContentAsString(StandardCharsets.UTF_8);
        assertThat(body).isEqualTo("meterId,timestamp,value\r\n");
    }

    @Test
    @DisplayName("AC-F36-2: After posting readings, export lists all meters in storage order; value uses toPlainString (e.g. 1E+3 -> 1000); each line ends with CRLF")
    void ac_f36_2_exports_posted_readings_in_order_with_plain_decimal_values() throws Exception {
        // Arrange: post three readings (two meters) in a known order; include scientific notation
        mvc.perform(post("/readings").contentType("application/json")
                .content("{\"meterId\":\"m1\",\"takenAt\":\"2026-01-01T00:00:00Z\",\"kwh\":12.5}"))
           .andExpect(status().isCreated());
        mvc.perform(post("/readings").contentType("application/json")
                .content("{\"meterId\":\"m2\",\"takenAt\":\"2026-01-02T00:00:00Z\",\"kwh\":1E+3}"))
           .andExpect(status().isCreated());
        mvc.perform(post("/readings").contentType("application/json")
                .content("{\"meterId\":\"m1\",\"takenAt\":\"2026-01-03T00:00:00Z\",\"kwh\":0}"))
           .andExpect(status().isCreated());

        // Act
        MvcResult res = mvc.perform(get("/readings/export"))
           .andExpect(status().isOk())
           .andExpect(content().contentTypeCompatibleWith("text/csv"))
           .andReturn();

        // Assert
        String body = res.getResponse().getContentAsString(StandardCharsets.UTF_8);
        assertThat(body).endsWith("\r\n");
        assertThat(body).startsWith("meterId,timestamp,value\r\n");
        String[] lines = body.split("\r\n");
        // header + 3 data lines
        assertThat(lines.length).isGreaterThanOrEqualTo(4);
        assertThat(lines[1]).isEqualTo("m1,2026-01-01T00:00:00Z,12.5");
        assertThat(lines[2]).isEqualTo("m2,2026-01-02T00:00:00Z,1000");
        assertThat(lines[3]).isEqualTo("m1,2026-01-03T00:00:00Z,0");
    }

    @Test
    @DisplayName("AC-F36-2: Readings removed by DELETE no longer appear in export; others remain")
    void ac_f36_2_deleted_meter_readings_are_absent() throws Exception {
        // Arrange: post readings for two meters; delete one
        mvc.perform(post("/readings").contentType("application/json")
                .content("{\"meterId\":\"m_del\",\"takenAt\":\"2026-01-01T00:00:00Z\",\"kwh\":1}"))
           .andExpect(status().isCreated());
        mvc.perform(post("/readings").contentType("application/json")
                .content("{\"meterId\":\"m_del\",\"takenAt\":\"2026-01-02T00:00:00Z\",\"kwh\":2}"))
           .andExpect(status().isCreated());
        mvc.perform(post("/readings").contentType("application/json")
                .content("{\"meterId\":\"m_keep\",\"takenAt\":\"2026-01-03T00:00:00Z\",\"kwh\":3}"))
           .andExpect(status().isCreated());

        mvc.perform(delete("/readings").param("meterId", "m_del"))
           .andExpect(status().isNoContent());

        // Act
        MvcResult res = mvc.perform(get("/readings/export"))
           .andExpect(status().isOk())
           .andExpect(content().contentTypeCompatibleWith("text/csv"))
           .andReturn();

        // Assert
        String body = res.getResponse().getContentAsString(StandardCharsets.UTF_8);
        assertThat(body).startsWith("meterId,timestamp,value\r\n");
        assertThat(body).contains("m_keep,2026-01-03T00:00:00Z,3");
        assertThat(body).doesNotContain("m_del,");

        String[] lines = body.split("\r\n");
        // header + 1 data line
        assertThat(lines.length).isGreaterThanOrEqualTo(2);
        assertThat(lines[1]).isEqualTo("m_keep,2026-01-03T00:00:00Z,3");
    }

    @Test
    @DisplayName("AC-F36-3: meterId containing comma or double quote is RFC 4180 quoted with inner quotes doubled; plain meterId remains unquoted")
    void ac_f36_3_quotes_meter_ids_with_commas_and_double_quotes() throws Exception {
        // Arrange: post meters with special characters and one plain
        mvc.perform(post("/readings").contentType("application/json")
                .content("{\"meterId\":\"a,b\",\"takenAt\":\"2026-01-01T00:00:00Z\",\"kwh\":3}"))
           .andExpect(status().isCreated());
        mvc.perform(post("/readings").contentType("application/json")
                .content("{\"meterId\":\"say \\\"hi\\\"\",\"takenAt\":\"2026-01-02T00:00:00Z\",\"kwh\":4}"))
           .andExpect(status().isCreated());
        mvc.perform(post("/readings").contentType("application/json")
                .content("{\"meterId\":\"m1\",\"takenAt\":\"2026-01-03T00:00:00Z\",\"kwh\":5}"))
           .andExpect(status().isCreated());

        // Act
        MvcResult res = mvc.perform(get("/readings/export"))
           .andExpect(status().isOk())
           .andExpect(content().contentTypeCompatibleWith("text/csv"))
           .andReturn();

        // Assert
        String body = res.getResponse().getContentAsString(StandardCharsets.UTF_8);
        String[] lines = body.split("\r\n");
        assertThat(lines.length).isGreaterThanOrEqualTo(4);
        assertThat(lines[1]).startsWith("\"a,b\",");
        assertThat(lines[2]).startsWith("\"say \"\"hi\"\"\",");
        assertThat(lines[3]).startsWith("m1,");
    }
}
