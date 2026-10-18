package com.example.pacs008.controller;

/** HTTP-style response returned by the controller: status code, content type and rendered body. */
public record Response(int status, String contentType, String body) {

    @Override
    public String toString() {
        return status + " " + body;
    }
}
