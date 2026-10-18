package com.example.pacs008.view;

import com.example.pacs008.service.ProcessingResult;

/** Renders a processing result for the caller. */
public interface PaymentView {

    String contentType();

    String render(ProcessingResult result);
}
