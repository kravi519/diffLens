package com.example.pacs008.mapper;

/** The message could not be read: not well-formed XML or not a pacs.008 document. */
public class MappingException extends RuntimeException {

    public MappingException(String message) {
        super(message);
    }

    public MappingException(String message, Throwable cause) {
        super(message, cause);
    }
}
