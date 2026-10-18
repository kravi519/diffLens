package com.example.pacs008.model;

/** One broken business rule: the CBPR+ rule id (e.g. R20) or a field check code, where, and why. */
public class ValidationError {

    private final String code;
    private final String path;
    private final String message;

    public ValidationError(String code, String path, String message) {
        this.code = code;
        this.path = path;
        this.message = message;
    }

    public String getCode() {
        return code;
    }

    public String getPath() {
        return path;
    }

    public String getMessage() {
        return message;
    }

    @Override
    public String toString() {
        return code + " " + path + ": " + message;
    }
}
