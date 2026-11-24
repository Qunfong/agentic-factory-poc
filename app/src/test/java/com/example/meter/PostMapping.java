package com.example.meter;

import org.springframework.core.annotation.AliasFor;

@org.springframework.web.bind.annotation.PostMapping
public @interface PostMapping {
    @AliasFor(annotation = org.springframework.web.bind.annotation.PostMapping.class, attribute = "value")
    String[] value() default {};
}
