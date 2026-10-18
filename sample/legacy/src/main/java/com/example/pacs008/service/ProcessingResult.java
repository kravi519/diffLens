package com.example.pacs008.service;

import com.example.pacs008.model.CreditTransferDto;
import com.example.pacs008.model.ValidationError;
import java.util.Collections;
import java.util.List;

/** Outcome of processing one pacs.008 message: the model handed from the service to the view. */
public class ProcessingResult {

    public enum Status { ACCEPTED, REJECTED }

    private final Status status;
    private final List<ValidationError> errors;
    private final CreditTransferDto payment;
    private final int storedRows;

    private ProcessingResult(Status status, List<ValidationError> errors, CreditTransferDto payment, int storedRows) {
        this.status = status;
        this.errors = errors;
        this.payment = payment;
        this.storedRows = storedRows;
    }

    static ProcessingResult accepted(CreditTransferDto payment, int storedRows) {
        return new ProcessingResult(Status.ACCEPTED, Collections.<ValidationError>emptyList(), payment, storedRows);
    }

    static ProcessingResult rejected(List<ValidationError> errors, int storedRows) {
        return new ProcessingResult(Status.REJECTED, errors, null, storedRows);
    }

    public Status getStatus() {
        return status;
    }

    public List<ValidationError> getErrors() {
        return errors;
    }

    public CreditTransferDto getPayment() {
        return payment;
    }

    public int getStoredRows() {
        return storedRows;
    }

    public boolean hasError(String code) {
        for (ValidationError error : errors) {
            if (error.getCode().equals(code)) {
                return true;
            }
        }
        return false;
    }
}
