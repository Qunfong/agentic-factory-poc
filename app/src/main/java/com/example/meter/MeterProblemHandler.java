package com.example.meter;

import java.net.URI;
import java.util.Comparator;
import java.util.List;
import java.util.stream.Stream;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.HttpStatusCode;
import org.springframework.http.MediaType;
import org.springframework.http.ProblemDetail;
import org.springframework.http.ResponseEntity;
import org.springframework.http.converter.HttpMessageNotReadableException;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.MissingServletRequestParameterException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.context.request.WebRequest;
import org.springframework.web.servlet.NoHandlerFoundException;
import org.springframework.web.servlet.mvc.method.annotation.ResponseEntityExceptionHandler;

/** Single place where every error becomes an RFC 9457 ProblemDetail sent as application/problem+json. */
@RestControllerAdvice
public class MeterProblemHandler extends ResponseEntityExceptionHandler {

    /** Every problem leaves here: forces Content-Type application/problem+json, fills a null detail from the title. */
    @Override
    protected ResponseEntity<Object> createResponseEntity(Object body, HttpHeaders headers,
                                                          HttpStatusCode status, WebRequest request) {
        if (body instanceof ProblemDetail problem) {
            fillDetail(problem);
            HttpHeaders problemHeaders = new HttpHeaders();
            if (headers != null) {
                problemHeaders.putAll(headers);
            }
            // a preset Content-Type skips Accept negotiation
            problemHeaders.setContentType(MediaType.APPLICATION_PROBLEM_JSON);
            return new ResponseEntity<>(problem, problemHeaders, status);
        }
        return super.createResponseEntity(body, headers, status, request);
    }

    @Override
    protected ResponseEntity<Object> handleMethodArgumentNotValid(MethodArgumentNotValidException ex, HttpHeaders headers,
                                                                  HttpStatusCode status, WebRequest request) {
        // a class-level constraint yields a global error; "" is the JSON Pointer of the whole body
        List<FieldError> errors = Stream.concat(
                        ex.getBindingResult().getFieldErrors().stream()
                                .map(e -> new FieldError(e.getField(), e.getDefaultMessage())),
                        ex.getBindingResult().getGlobalErrors().stream()
                                .map(e -> new FieldError("", e.getDefaultMessage())))
                .toList();
        return validationFailed(ex, errors, headers, request);
    }

    @Override
    protected ResponseEntity<Object> handleMissingServletRequestParameter(MissingServletRequestParameterException ex, HttpHeaders headers,
                                                                          HttpStatusCode status, WebRequest request) {
        List<FieldError> errors = List.of(new FieldError(ex.getParameterName(), "is required"));
        return validationFailed(ex, errors, headers, request);
    }

    /** 400 /problems/validation-failed with errors sorted by field, then message; detail names the fields, or gives the class-level messages if there are none. */
    private ResponseEntity<Object> validationFailed(Exception ex, List<FieldError> errors, HttpHeaders headers,
                                                    WebRequest request) {
        List<FieldError> sorted = errors.stream()
                .sorted(Comparator.comparing(FieldError::field)
                        .thenComparing(FieldError::message, Comparator.nullsFirst(Comparator.naturalOrder())))
                .toList();
        List<String> fields = sorted.stream().map(FieldError::field).filter(f -> !f.isEmpty()).distinct().toList();
        String detail = fields.isEmpty()
                ? "Invalid request: " + String.join("; ", sorted.stream().map(FieldError::message).distinct().toList())
                : "Invalid field(s): " + String.join(", ", fields);
        ProblemDetail problem = ProblemDetail.forStatusAndDetail(HttpStatus.BAD_REQUEST, detail);
        problem.setType(URI.create("/problems/validation-failed"));
        problem.setTitle("Invalid request");
        problem.setProperty("errors", sorted);
        return handleExceptionInternal(ex, problem, headers, HttpStatus.BAD_REQUEST, request);
    }

    @Override
    protected ResponseEntity<Object> handleHttpMessageNotReadable(HttpMessageNotReadableException ex, HttpHeaders headers,
                                                                  HttpStatusCode status, WebRequest request) {
        ProblemDetail problem = ProblemDetail.forStatusAndDetail(HttpStatus.BAD_REQUEST,
                "The request body is not valid JSON or does not match the expected shape");
        problem.setType(URI.create("/problems/malformed-request"));
        problem.setTitle("Malformed request body");
        return handleExceptionInternal(ex, problem, headers, HttpStatus.BAD_REQUEST, request);
    }

    @Override
    protected ResponseEntity<Object> handleNoHandlerFoundException(NoHandlerFoundException ex, HttpHeaders headers,
                                                                   HttpStatusCode status, WebRequest request) {
        ProblemDetail problem = ProblemDetail.forStatusAndDetail(HttpStatus.NOT_FOUND,
                "No endpoint " + ex.getHttpMethod() + " " + ex.getRequestURL());
        problem.setType(URI.create("/problems/not-found"));
        problem.setTitle("Not Found");
        return handleExceptionInternal(ex, problem, headers, HttpStatus.NOT_FOUND, request);
    }

    @ExceptionHandler
    ResponseEntity<ProblemDetail> alreadyRegistered(MeterAlreadyRegisteredException e) {
        ProblemDetail problem = ProblemDetail.forStatusAndDetail(HttpStatus.CONFLICT, e.getMessage());
        problem.setType(URI.create("/problems/meter-already-registered"));
        problem.setTitle("Meter already registered");
        fillDetail(problem);
        return ResponseEntity.status(HttpStatus.CONFLICT).contentType(MediaType.APPLICATION_PROBLEM_JSON).body(problem);
    }

    private static void fillDetail(ProblemDetail problem) {
        if (problem.getDetail() == null) {
            problem.setDetail(problem.getTitle());
        }
    }

    @ExceptionHandler
    ProblemDetail notFound(MeterNotFoundException e) {
        ProblemDetail problem = ProblemDetail.forStatusAndDetail(HttpStatus.NOT_FOUND, e.getMessage());
        problem.setType(URI.create("/problems/meter-not-found"));
        problem.setTitle("Meter not found");
        return problem;
    }
}
