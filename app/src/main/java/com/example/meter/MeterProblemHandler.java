package com.example.meter;

import java.net.URI;
import org.springframework.http.HttpStatus;
import org.springframework.http.ProblemDetail;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.servlet.mvc.method.annotation.ResponseEntityExceptionHandler;

/** Extends ResponseEntityExceptionHandler so validation and unreadable-body 400s are also ProblemDetail (about:blank). */
@RestControllerAdvice
public class MeterProblemHandler extends ResponseEntityExceptionHandler {

    @ExceptionHandler
    ProblemDetail alreadyRegistered(MeterAlreadyRegisteredException e) {
        ProblemDetail problem = ProblemDetail.forStatusAndDetail(HttpStatus.CONFLICT, e.getMessage());
        problem.setType(URI.create("/problems/meter-already-registered"));
        problem.setTitle("Meter already registered");
        return problem;
    }

    @ExceptionHandler
    ProblemDetail notFound(MeterNotFoundException e) {
        ProblemDetail problem = ProblemDetail.forStatusAndDetail(HttpStatus.NOT_FOUND, e.getMessage());
        problem.setType(URI.create("/problems/meter-not-found"));
        problem.setTitle("Meter not found");
        return problem;
    }
}
