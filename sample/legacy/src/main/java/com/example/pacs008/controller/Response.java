package com.example.pacs008.controller;

/** HTTP-style response returned by the controller: status code, content type and rendered body. */
public class Response {

    private final int status;
    private final String contentType;
    private final String body;

    public Response(int status, String contentType, String body) {
        this.status = status;
        this.contentType = contentType;
        this.body = body;
    }

    public int getStatus() {
        return status;
    }

    public String getContentType() {
        return contentType;
    }

    public String getBody() {
        return body;
    }

    @Override
    public String toString() {
        return status + " " + body;
    }
}
