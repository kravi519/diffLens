package com.example.pacs008.service;

import com.example.pacs008.mapper.MappingException;
import com.example.pacs008.mapper.Pacs008DtoConverter;
import com.example.pacs008.mapper.Pacs008XmlMapper;
import com.example.pacs008.model.CreditTransferDto;
import com.example.pacs008.model.Pacs008Message;
import com.example.pacs008.model.ValidationError;
import com.example.pacs008.repository.DuplicateKeyException;
import com.example.pacs008.repository.PaymentRepository;
import com.example.pacs008.validation.Pacs008Validator;
import java.util.Collections;
import java.util.List;

/** Legacy (Java 8) pacs.008 business service: map XML, validate business rules, convert to DTO, save. */
public class Pacs008Service {

    private final Pacs008XmlMapper mapper = new Pacs008XmlMapper();
    private final Pacs008Validator validator = new Pacs008Validator();
    private final Pacs008DtoConverter converter = new Pacs008DtoConverter();
    private final PaymentRepository repository;

    public Pacs008Service(PaymentRepository repository) {
        this.repository = repository;
    }

    public ProcessingResult process(String xml) {
        Pacs008Message message;
        try {
            message = mapper.map(xml);
        } catch (MappingException e) {
            return ProcessingResult.rejected(single("PARSE", "/", e.getMessage()), repository.count());
        }
        List<ValidationError> errors = validator.validate(message);
        if (!errors.isEmpty()) {
            return ProcessingResult.rejected(errors, repository.count());
        }
        CreditTransferDto payment = converter.convert(message);
        try {
            repository.save(payment);
        } catch (DuplicateKeyException e) {
            return ProcessingResult.rejected(single("DUPLICATE", "GrpHdr/MsgId", e.getMessage()), repository.count());
        }
        return ProcessingResult.accepted(payment, repository.count());
    }

    private static List<ValidationError> single(String code, String path, String message) {
        return Collections.singletonList(new ValidationError(code, path, message));
    }
}
