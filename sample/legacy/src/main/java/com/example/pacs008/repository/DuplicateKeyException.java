package com.example.pacs008.repository;

/** A row with the same primary key is already stored. */
public class DuplicateKeyException extends Exception {

    public DuplicateKeyException(String message) {
        super(message);
    }
}
