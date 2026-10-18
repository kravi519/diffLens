package com.example.pacs008;

import static org.junit.jupiter.api.Assertions.assertEquals;

import com.example.pacs008.controller.Pacs008Controller;
import com.example.pacs008.controller.Response;
import com.example.pacs008.repository.InMemoryPaymentRepository;
import com.example.pacs008.service.Pacs008Service;
import com.example.pacs008.view.TextPaymentView;
import java.io.ByteArrayOutputStream;
import java.io.FileNotFoundException;
import java.io.IOException;
import java.io.InputStream;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvFileSource;

/**
 * Legacy pacs.008 suite (Java 8). Each case posts one or more shared messages from sample/inputs/pacs008
 * to the controller, backed by a fresh virtual DB, and records the last response.
 */
class Pacs008ControllerTest {

    @ParameterizedTest(name = "{arguments}")
    @CsvFileSource(resources = "/pacs008.csv", numLinesToSkip = 1)
    void submitPacs008(final String caseId, final String files, String expected) {
        assertEquals(expected, Recorder.capture(caseId, new Recorder.Call() {
            public Object run() throws Exception {
                Pacs008Controller controller = new Pacs008Controller(
                        new Pacs008Service(new InMemoryPaymentRepository()), new TextPaymentView());
                Response response = null;
                for (String file : files.split(";")) {
                    response = controller.submit(resource("/pacs008/" + file.trim()));
                }
                return response;
            }
        }));
    }

    private static String resource(String name) throws IOException {
        InputStream in = Pacs008ControllerTest.class.getResourceAsStream(name);
        if (in == null) {
            throw new FileNotFoundException(name);
        }
        try {
            ByteArrayOutputStream out = new ByteArrayOutputStream();
            byte[] buffer = new byte[4096];
            int n;
            while ((n = in.read(buffer)) != -1) {
                out.write(buffer, 0, n);
            }
            return new String(out.toByteArray(), "UTF-8");
        } finally {
            in.close();
        }
    }
}
