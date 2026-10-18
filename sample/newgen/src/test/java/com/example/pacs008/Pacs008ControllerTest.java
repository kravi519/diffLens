package com.example.pacs008;

import static org.junit.jupiter.api.Assertions.assertEquals;

import com.example.pacs008.controller.Pacs008Controller;
import com.example.pacs008.controller.Response;
import com.example.pacs008.repository.InMemoryPaymentRepository;
import com.example.pacs008.service.Pacs008Service;
import com.example.pacs008.view.TextPaymentView;
import java.io.FileNotFoundException;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvFileSource;

/**
 * New-gen pacs.008 suite. Each case posts one or more shared messages from sample/inputs/pacs008 to the
 * controller, backed by a fresh virtual DB, and records the last response.
 */
class Pacs008ControllerTest {

    @ParameterizedTest(name = "{arguments}")
    @CsvFileSource(resources = "/pacs008.csv", numLinesToSkip = 1)
    void submit(String caseId, String files, String expected) {
        assertEquals(expected, post(caseId, files));
    }

    /** Bulk cases have no expected result: the output is only recorded and compared with legacy. */
    @ParameterizedTest(name = "{arguments}")
    @CsvFileSource(resources = "/pacs008_bulk.csv", numLinesToSkip = 1)
    void bulk(String caseId, String files, String expected) {
        String actual = post(caseId, files);
        if (expected != null) {
            assertEquals(expected, actual);
        }
    }

    private static String post(String caseId, String files) {
        return Recorder.capture(caseId, () -> {
            var controller = new Pacs008Controller(
                    new Pacs008Service(new InMemoryPaymentRepository()), new TextPaymentView());
            Response response = null;
            for (var file : files.split(";")) {
                response = controller.submit(resource("/pacs008/" + file.strip()));
            }
            return response;
        });
    }

    private static String resource(String name) throws IOException {
        try (var in = Pacs008ControllerTest.class.getResourceAsStream(name)) {
            if (in == null) {
                throw new FileNotFoundException(name);
            }
            return new String(in.readAllBytes(), StandardCharsets.UTF_8);
        }
    }
}
