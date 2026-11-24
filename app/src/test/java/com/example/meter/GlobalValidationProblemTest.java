package com.example.meter;

import jakarta.validation.Constraint;
import jakarta.validation.ConstraintValidator;
import jakarta.validation.ConstraintValidatorContext;
import jakarta.validation.Payload;
import jakarta.validation.constraints.NotBlank;
import java.lang.annotation.Documented;
import java.lang.annotation.Retention;
import java.lang.annotation.Target;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.context.annotation.Import;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.request.MockMvcRequestBuilders;
import org.springframework.test.web.servlet.result.MockMvcResultMatchers;

import static java.lang.annotation.ElementType.TYPE;
import static java.lang.annotation.RetentionPolicy.RUNTIME;
import static org.hamcrest.Matchers.containsString;
import static org.hamcrest.Matchers.not;

@WebMvcTest
@Import({MeterService.class, GlobalValidationProblemTest.TestController.class})
class GlobalValidationProblemTest {

    @Autowired
    MockMvc mvc;

    @Test
    @Tag("AC-F60-1")
    @DisplayName("AC-F60-1: class-level constraint violation appears in errors[] with field '' and detail starts 'Invalid request:'")
    void ac_f60_1_class_level_violation_only_reported_with_empty_field() throws Exception {
        // id does not start with type -> class-level violation only
        mvc.perform(MockMvcRequestBuilders.post("/test-global")
                .contentType(MediaType.APPLICATION_JSON)
                .content("{\"id\": \"abc\", \"type\": \"z\"}"))
            .andExpect(MockMvcResultMatchers.status().isBadRequest())
            .andExpect(MockMvcResultMatchers.content().contentTypeCompatibleWith(MediaType.APPLICATION_PROBLEM_JSON))
            .andExpect(MockMvcResultMatchers.jsonPath("$.type").value("/problems/validation-failed"))
            .andExpect(MockMvcResultMatchers.jsonPath("$.status").value(400))
            .andExpect(MockMvcResultMatchers.jsonPath("$.errors[0].field").value(""))
            .andExpect(MockMvcResultMatchers.jsonPath("$.errors[0].message").value("id must start with type"))
            .andExpect(MockMvcResultMatchers.jsonPath("$.detail").value(containsString("Invalid request:")));
    }

    @Test
    @Tag("AC-F60-1")
    @DisplayName("AC-F60-1: class-level and field-level violations are both listed; class-level first; detail lists only named fields")
    void ac_f60_1_class_level_and_field_violation_listed_together() throws Exception {
        // id blank -> field-level violation; also fails class-level constraint
        mvc.perform(MockMvcRequestBuilders.post("/test-global")
                .contentType(MediaType.APPLICATION_JSON)
                .content("{\"id\": \"\", \"type\": \"z\"}"))
            .andExpect(MockMvcResultMatchers.status().isBadRequest())
            .andExpect(MockMvcResultMatchers.content().contentTypeCompatibleWith(MediaType.APPLICATION_PROBLEM_JSON))
            .andExpect(MockMvcResultMatchers.jsonPath("$.type").value("/problems/validation-failed"))
            .andExpect(MockMvcResultMatchers.jsonPath("$.status").value(400))
            .andExpect(MockMvcResultMatchers.jsonPath("$.errors[0].field").value(""))
            .andExpect(MockMvcResultMatchers.jsonPath("$.errors[1].field").value("id"))
            .andExpect(MockMvcResultMatchers.jsonPath("$.detail").value("Invalid field(s): id"));
    }

    @Test
    @Tag("AC-F60-2")
    @DisplayName("AC-F60-2: missing required request parameter 'meterId' reports message 'is required' and not 'must not be null'")
    void ac_f60_2_missing_meter_id_param_is_required() throws Exception {
        mvc.perform(MockMvcRequestBuilders.delete("/readings"))
            .andExpect(MockMvcResultMatchers.status().isBadRequest())
            .andExpect(MockMvcResultMatchers.content().contentTypeCompatibleWith(MediaType.APPLICATION_PROBLEM_JSON))
            .andExpect(MockMvcResultMatchers.jsonPath("$.type").value("/problems/validation-failed"))
            .andExpect(MockMvcResultMatchers.jsonPath("$.status").value(400))
            .andExpect(MockMvcResultMatchers.jsonPath("$.errors[0].field").value("meterId"))
            .andExpect(MockMvcResultMatchers.jsonPath("$.errors[0].message").value("is required"))
            .andExpect(MockMvcResultMatchers.jsonPath("$.detail").value(containsString("meterId")))
            .andExpect(MockMvcResultMatchers.content().string(not(containsString("must not be null"))));
    }

    // Test-only controller and class-level constraint used to prove AC-F60-1
    @RestController
    static class TestController {
        @PostMapping("/test-global")
        public TestRequest register(@jakarta.validation.Valid @org.springframework.web.bind.annotation.RequestBody TestRequest body) {
            return body;
        }
    }

    @ValidCombination
    public record TestRequest(@NotBlank String id, @NotBlank String type) { }

    @Documented
    @Constraint(validatedBy = ValidCombinationValidator.class)
    @Target({TYPE})
    @Retention(RUNTIME)
    public @interface ValidCombination {
        String message() default "id must start with type";
        Class<?>[] groups() default {};
        Class<? extends Payload>[] payload() default {};
    }

    public static class ValidCombinationValidator implements ConstraintValidator<ValidCombination, TestRequest> {
        @Override
        public boolean isValid(TestRequest value, ConstraintValidatorContext context) {
            if (value == null) return true; // not this constraint's concern
            if (value.id() == null || value.type() == null) return true; // let field-level constraints handle nulls
            return value.id().startsWith(value.type());
        }
    }
}
