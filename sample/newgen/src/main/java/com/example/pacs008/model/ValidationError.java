package com.example.pacs008.model;

/** One broken business rule: the CBPR+ rule id (e.g. R20) or a field check code, where, and why. */
public record ValidationError(String code, String path, String message) {
}
