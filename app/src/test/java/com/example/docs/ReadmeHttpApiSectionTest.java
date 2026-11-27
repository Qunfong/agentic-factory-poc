package com.example.docs;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.Assertions;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Arrays;

public class ReadmeHttpApiSectionTest {

    private String readReadme() {
        try {
            // The app module runs under app/, README.md is at the repository root.
            Path readme = Path.of("..", "README.md");
            String content = Files.readString(readme, StandardCharsets.UTF_8);
            // Normalize line endings to \n for consistent substring matching
            content = content.replace("\r\n", "\n").replace("\r", "\n");
            return content;
        } catch (IOException e) {
            throw new RuntimeException("Could not read README.md from repository root", e);
        }
    }

    private boolean lineHas(String line, String... tokens) {
        return Arrays.stream(tokens).allMatch(line::contains);
    }

    @Test
    void ac_f35_1_lists_endpoints() {
        String readme = readReadme();
        Assertions.assertTrue(readme.contains("## HTTP API"), "README.md should contain heading '## HTTP API'");

        Assertions.assertTrue(readme.contains("POST /meters"), "README.md should list POST /meters endpoint");
        Assertions.assertTrue(readme.contains("POST /readings"), "README.md should list POST /readings endpoint");
        Assertions.assertTrue(readme.contains("GET /readings?meterId="), "README.md should list GET /readings?meterId= endpoint");
        Assertions.assertTrue(readme.contains("GET /readings/count"), "README.md should list GET /readings/count endpoint");
        Assertions.assertTrue(readme.contains("DELETE /readings?meterId="), "README.md should list DELETE /readings?meterId= endpoint");
    }

    @Test
    void ac_f35_2_names_status_codes() {
        String readme = readReadme();
        String[] lines = readme.split("\n");

        boolean metersRowOk = false;
        boolean readingsPostRowOk = false;
        boolean readingsGetRowOk = false;
        boolean readingsCountRowOk = false;
        boolean readingsDeleteRowOk = false;

        for (String line : lines) {
            String trimmed = line.trim();
            if (trimmed.contains("/meters") && trimmed.contains("POST")) {
                if (lineHas(trimmed, "201", "400", "409")) {
                    metersRowOk = true;
                }
            }
            if (trimmed.contains("/readings") && trimmed.contains("POST") && !trimmed.contains("?meterId=")) {
                if (lineHas(trimmed, "201", "400")) {
                    readingsPostRowOk = true;
                }
            }
            if (trimmed.contains("/readings?meterId=") && trimmed.contains("GET")) {
                if (lineHas(trimmed, "200", "400")) {
                    readingsGetRowOk = true;
                }
            }
            if (trimmed.contains("/readings/count") && trimmed.contains("GET")) {
                if ((trimmed.contains("none specific") || trimmed.contains("no endpoint-specific error")) && trimmed.contains("200")) {
                    readingsCountRowOk = true;
                }
            }
            if (trimmed.contains("/readings?meterId=") && trimmed.contains("DELETE")) {
                if (lineHas(trimmed, "204", "400")) {
                    readingsDeleteRowOk = true;
                }
            }
        }

        Assertions.assertTrue(metersRowOk, "README.md should name success 201 and error 400, 409 for POST /meters");
        Assertions.assertTrue(readingsPostRowOk, "README.md should name success 201 and error 400 for POST /readings");
        Assertions.assertTrue(readingsGetRowOk, "README.md should name success 200 and error 400 for GET /readings?meterId=");
        Assertions.assertTrue(readingsCountRowOk, "README.md should name success 200 and explicitly state none specific error for GET /readings/count");
        Assertions.assertTrue(readingsDeleteRowOk, "README.md should name success 204 and error 400 for DELETE /readings?meterId=");
    }

    @Test
    void ac_f35_3_shows_curl_examples() {
        String readme = readReadme();

        // Expect the exact curl examples from the spec, including line continuations and headers
        String registerMeterCurl = "curl -i -X POST http://localhost:8080/meters \\\n  -H 'Content-Type: application/json' \\\n  -d '{\"id\": \"m-1\", \"type\": \"electricity\"}'";

        String postReadingCurl = "curl -i -X POST http://localhost:8080/readings \\\n  -H 'Content-Type: application/json' \\\n  -d '{\"meterId\": \"m-1\", \"takenAt\": \"2026-01-01T00:00:00Z\", \"kwh\": 12.5}'";

        Assertions.assertTrue(readme.contains(registerMeterCurl), "README.md should include curl example to register a meter against http://localhost:8080");
        Assertions.assertTrue(readme.contains(postReadingCurl), "README.md should include curl example to post a reading against http://localhost:8080");

        // Ensure exactly one of each example is present
        Assertions.assertEquals(1, countOccurrences(readme, "curl -i -X POST http://localhost:8080/meters"), "README.md should have exactly one meter registration curl example");
        Assertions.assertEquals(1, countOccurrences(readme, "curl -i -X POST http://localhost:8080/readings"), "README.md should have exactly one reading post curl example");

        // Check fenced bash blocks are used at least once
        Assertions.assertTrue(readme.contains("```bash"), "README.md should use fenced bash blocks for curl examples");
    }

    private int countOccurrences(String haystack, String needle) {
        int count = 0;
        int idx = 0;
        while ((idx = haystack.indexOf(needle, idx)) != -1) {
            count++;
            idx += needle.length();
        }
        return count;
    }
}
