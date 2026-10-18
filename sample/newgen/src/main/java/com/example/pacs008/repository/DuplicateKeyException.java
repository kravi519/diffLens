package com.example.pacs008.repository;

/** A row with the same unique key is already stored. */
public class DuplicateKeyException extends RuntimeException {

    public DuplicateKeyException(String message) {
        super(message);
    }
}
