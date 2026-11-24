package com.example.meter;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@WebMvcTest(ReadingController.class)
class ReadingRangePageTest {

    @Autowired
    MockMvc mvc;

    private void postReading(String meterId, String takenAt, String kwh) throws Exception {
        String body = "{\"meterId\":\"" + meterId + "\",\"takenAt\":\"" + takenAt + "\",\"kwh\":" + kwh + "}";
        mvc.perform(post("/readings").contentType(MediaType.APPLICATION_JSON).content(body))
            .andExpect(status().isCreated());
    }

    // AC-F33-1: inclusive range filter with both bounds
    @Test
    @DisplayName("AC-F33-1 inclusive from/to include bounds and filter others")
    void ac_f33_1_inclusive_range() throws Exception {
        String meterId = "m-f33-1-range";
        String t1 = "2031-01-01T00:00:00Z";
        String t2 = "2031-01-01T01:00:00Z";
        String t3 = "2031-01-01T02:00:00Z";
        postReading(meterId, t1, "1.0");
        postReading(meterId, t2, "2.0");
        postReading(meterId, t3, "3.0");

        mvc.perform(get("/readings")
                .param("meterId", meterId)
                .param("from", t1)
                .param("to", t2))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$[0].takenAt").value(t1))
            .andExpect(jsonPath("$[1].takenAt").value(t2))
            .andExpect(jsonPath("$[2]").doesNotExist());
    }

    // AC-F33-1: only from
    @Test
    @DisplayName("AC-F33-1 only from returns readings with takenAt >= from")
    void ac_f33_1_only_from() throws Exception {
        String meterId = "m-f33-1-only-from";
        String t1 = "2031-01-02T00:00:00Z";
        String t2 = "2031-01-02T01:00:00Z";
        String t3 = "2031-01-02T02:00:00Z";
        postReading(meterId, t1, "1.0");
        postReading(meterId, t2, "2.0");
        postReading(meterId, t3, "3.0");

        mvc.perform(get("/readings")
                .param("meterId", meterId)
                .param("from", t2))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$[0].takenAt").value(t2))
            .andExpect(jsonPath("$[1].takenAt").value(t3))
            .andExpect(jsonPath("$[2]").doesNotExist());
    }

    // AC-F33-1: only to
    @Test
    @DisplayName("AC-F33-1 only to returns readings with takenAt <= to")
    void ac_f33_1_only_to() throws Exception {
        String meterId = "m-f33-1-only-to";
        String t1 = "2031-01-03T00:00:00Z";
        String t2 = "2031-01-03T01:00:00Z";
        String t3 = "2031-01-03T02:00:00Z";
        postReading(meterId, t1, "1.0");
        postReading(meterId, t2, "2.0");
        postReading(meterId, t3, "3.0");

        mvc.perform(get("/readings")
                .param("meterId", meterId)
                .param("to", t2))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$[0].takenAt").value(t1))
            .andExpect(jsonPath("$[1].takenAt").value(t2))
            .andExpect(jsonPath("$[2]").doesNotExist());
    }

    // AC-F33-1: offset form equals Z bound
    @Test
    @DisplayName("AC-F33-1 offset bound equals Z instant and includes exact takenAt")
    void ac_f33_1_offset_bound_equivalence() throws Exception {
        String meterId = "m-f33-1-offset";
        String tz = "2026-01-01T00:00:00Z";
        String offset = "2026-01-01T01:00:00+01:00"; // equivalent to tz
        postReading(meterId, tz, "5.0");

        mvc.perform(get("/readings")
                .param("meterId", meterId)
                .param("from", offset))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$[0].takenAt").value(tz))
            .andExpect(jsonPath("$[1]").doesNotExist());
    }

    // AC-F33-1: meterId optional, filters across all meters
    @Test
    @DisplayName("AC-F33-1 meterId optional: filters by range across meters")
    void ac_f33_1_no_meterId_works() throws Exception {
        String m1 = "m-f33-1-nomid-1";
        String m2 = "m-f33-1-nomid-2";
        String t0 = "2032-01-01T00:00:00Z";
        String t2 = "2032-01-01T02:00:00Z";
        String t3 = "2032-01-01T03:00:00Z";
        postReading(m1, t0, "1.0");
        postReading(m2, t2, "2.0");
        postReading(m1, t3, "3.0");

        mvc.perform(get("/readings")
                .param("from", t0)
                .param("to", t2))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$[0].takenAt").value(t0))
            .andExpect(jsonPath("$[1].takenAt").value(t2))
            .andExpect(jsonPath("$[2]").doesNotExist());
    }

    // AC-F33-2: default page returns first 20 in ascending takenAt order
    @Test
    @DisplayName("AC-F33-2 default returns first 20 readings in ascending takenAt order")
    void ac_f33_2_default_first_20_ascending() throws Exception {
        String meterId = "m-f33-2-default-asc";
        // Insert 25 readings out of order: newest first
        for (int i = 24; i >= 0; i--) {
            String takenAt = String.format("2033-01-01T%02d:00:00Z", i);
            postReading(meterId, takenAt, String.valueOf(i));
        }
        // First page (default size=20) should have 20 earliest takenAt values 00..19
        mvc.perform(get("/readings").param("meterId", meterId))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$[0].takenAt").value("2033-01-01T00:00:00Z"))
            .andExpect(jsonPath("$[19].takenAt").value("2033-01-01T19:00:00Z"))
            .andExpect(jsonPath("$[20]").doesNotExist());

        // Second page should have the remaining 5: 20..24
        mvc.perform(get("/readings").param("meterId", meterId).param("page", "1"))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$[0].takenAt").value("2033-01-01T20:00:00Z"))
            .andExpect(jsonPath("$[4].takenAt").value("2033-01-01T24:00:00Z"))
            .andExpect(jsonPath("$[5]").doesNotExist());
    }

    // AC-F33-2: size=100 allowed and returns up to 100 readings
    @Test
    @DisplayName("AC-F33-2 size=100 allowed returns up to 100 readings")
    void ac_f33_2_size_100_allowed() throws Exception {
        String meterId = "m-f33-2-size100";
        for (int i = 0; i < 60; i++) {
            String takenAt = String.format("2034-01-01T%02d:00:00Z", i);
            postReading(meterId, takenAt, "1.0");
        }
        mvc.perform(get("/readings").param("meterId", meterId).param("size", "100"))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$[59].takenAt").value("2034-01-01T59:00:00Z"))
            .andExpect(jsonPath("$[60]").doesNotExist());
    }

    // AC-F33-2: page past the end returns []
    @Test
    @DisplayName("AC-F33-2 page past end returns empty array")
    void ac_f33_2_page_past_end_empty() throws Exception {
        String meterId = "m-f33-2-past-end";
        postReading(meterId, "2035-01-01T00:00:00Z", "1.0");
        postReading(meterId, "2035-01-01T01:00:00Z", "1.0");
        postReading(meterId, "2035-01-01T02:00:00Z", "1.0");
        mvc.perform(get("/readings").param("meterId", meterId).param("page", "2").param("size", "2"))
            .andExpect(status().isOk())
            .andExpect(content().json("[]"));
    }

    // AC-F33-2: stable sort keeps insertion order for equal timestamps across pages
    @Test
    @DisplayName("AC-F33-2 stable sort: equal takenAt keep insertion order across pages")
    void ac_f33_2_stable_sort_equal_timestamps() throws Exception {
        String meterId = "m-f33-2-stable";
        String t0 = "2036-01-01T00:00:00Z";
        String ts = "2036-01-01T01:00:00Z";
        String t2 = "2036-01-01T02:00:00Z";
        // Insert with same timestamp in a specific order
        postReading(meterId, t0, "1.0");          // earliest
        postReading(meterId, ts, "2.0");          // A
        postReading(meterId, ts, "3.0");          // B
        postReading(meterId, ts, "4.0");          // C
        postReading(meterId, t2, "5.0");          // latest

        // Page size 2: page0 -> t0, A; page1 -> B, C
        mvc.perform(get("/readings").param("meterId", meterId).param("size", "2"))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$[0].takenAt").value(t0))
            .andExpect(jsonPath("$[1].kwh").value(2.0)); // A

        mvc.perform(get("/readings").param("meterId", meterId).param("size", "2").param("page", "1"))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$[0].kwh").value(3.0)) // B
            .andExpect(jsonPath("$[1].kwh").value(4.0)); // C
    }

    // AC-F33-3: invalid parameters yield 400 ProblemDetail
    @Test
    @DisplayName("AC-F33-3 size above 100 yields 400 ProblemDetail")
    void ac_f33_3_reject_size_above_100() throws Exception {
        mvc.perform(get("/readings").param("size", "101"))
            .andExpect(status().isBadRequest())
            .andExpect(content().contentTypeCompatibleWith("application/problem+json"));
    }

    @Test
    @DisplayName("AC-F33-3 negative page yields 400 ProblemDetail")
    void ac_f33_3_reject_negative_page() throws Exception {
        mvc.perform(get("/readings").param("page", "-1"))
            .andExpect(status().isBadRequest())
            .andExpect(content().contentTypeCompatibleWith("application/problem+json"));
    }

    @Test
    @DisplayName("AC-F33-3 unparsable from yields 400 ProblemDetail")
    void ac_f33_3_reject_unparsable_from() throws Exception {
        mvc.perform(get("/readings").param("from", "not-a-date"))
            .andExpect(status().isBadRequest())
            .andExpect(content().contentTypeCompatibleWith("application/problem+json"));
    }

    @Test
    @DisplayName("AC-F33-3 date without time in to yields 400 ProblemDetail")
    void ac_f33_3_reject_date_without_time_to() throws Exception {
        mvc.perform(get("/readings").param("to", "2026-01-01"))
            .andExpect(status().isBadRequest())
            .andExpect(content().contentTypeCompatibleWith("application/problem+json"));
    }

    @Test
    @DisplayName("AC-F33-3 size=100 is accepted")
    void ac_f33_3_size_100_ok() throws Exception {
        mvc.perform(get("/readings").param("size", "100"))
            .andExpect(status().isOk());
    }

    @Test
    @DisplayName("AC-F33-3 page=0 is accepted")
    void ac_f33_3_page_0_ok() throws Exception {
        mvc.perform(get("/readings").param("page", "0"))
            .andExpect(status().isOk());
    }
}
