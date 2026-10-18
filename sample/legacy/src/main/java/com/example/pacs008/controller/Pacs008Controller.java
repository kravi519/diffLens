package com.example.pacs008.controller;

import com.example.pacs008.service.Pacs008Service;
import com.example.pacs008.service.ProcessingResult;
import com.example.pacs008.view.PaymentView;

/**
 * Legacy (Java 8) controller for POST /payments/pacs008: hands the request body to the service and the
 * result to the view, and picks the HTTP status.
 */
public class Pacs008Controller {

    public static final int CREATED = 201;
    public static final int BAD_REQUEST = 400;
    public static final int CONFLICT = 409;
    public static final int UNPROCESSABLE = 422;

    private final Pacs008Service service;
    private final PaymentView view;

    public Pacs008Controller(Pacs008Service service, PaymentView view) {
        this.service = service;
        this.view = view;
    }

    public Response submit(String xml) {
        ProcessingResult result = service.process(xml);
        return new Response(status(result), view.contentType(), view.render(result));
    }

    private static int status(ProcessingResult result) {
        if (result.getStatus() == ProcessingResult.Status.ACCEPTED) {
            return CREATED;
        }
        if (result.hasError("PARSE")) {
            return BAD_REQUEST;
        }
        if (result.hasError("DUPLICATE")) {
            return CONFLICT;
        }
        return UNPROCESSABLE;
    }
}
