package com.example.meter;

import static com.tngtech.archunit.lang.syntax.ArchRuleDefinition.noClasses;

import com.tngtech.archunit.core.domain.JavaClasses;
import com.tngtech.archunit.core.importer.ClassFileImporter;
import com.tngtech.archunit.core.importer.ImportOption;
import com.tngtech.archunit.library.GeneralCodingRules;
import org.junit.jupiter.api.Test;
import org.springframework.stereotype.Controller;
import org.springframework.stereotype.Repository;

class ArchitectureTest {

    private static final JavaClasses PRODUCTION = new ClassFileImporter()
            .withImportOption(ImportOption.Predefined.DO_NOT_INCLUDE_TESTS)
            .importPackages("com.example.meter");

    @Test
    void no_standard_streams() {
        GeneralCodingRules.NO_CLASSES_SHOULD_ACCESS_STANDARD_STREAMS.check(PRODUCTION);
    }

    @Test
    void no_field_injection() {
        GeneralCodingRules.NO_CLASSES_SHOULD_USE_FIELD_INJECTION.check(PRODUCTION);
    }

    @Test
    void controllers_do_not_call_repositories() {
        noClasses()
                .that().areMetaAnnotatedWith(Controller.class)
                .should().dependOnClassesThat().areAnnotatedWith(Repository.class)
                .orShould().dependOnClassesThat().areAssignableTo("org.springframework.data.repository.Repository")
                .allowEmptyShould(true)
                .check(PRODUCTION);
    }
}
