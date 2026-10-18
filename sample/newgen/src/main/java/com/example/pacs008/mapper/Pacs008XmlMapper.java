package com.example.pacs008.mapper;

import com.example.pacs008.model.Pacs008Message;
import com.example.pacs008.model.Pacs008Message.AppHeader;
import com.example.pacs008.model.Pacs008Message.Charge;
import com.example.pacs008.model.Pacs008Message.GroupHeader;
import com.example.pacs008.model.Pacs008Message.Party;
import com.example.pacs008.model.Pacs008Message.PostalAddress;
import com.example.pacs008.model.Pacs008Message.Transaction;
import java.io.StringReader;
import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.List;
import java.util.Optional;
import javax.xml.XMLConstants;
import javax.xml.parsers.DocumentBuilderFactory;
import org.w3c.dom.Document;
import org.w3c.dom.Element;
import org.w3c.dom.Node;
import org.xml.sax.ErrorHandler;
import org.xml.sax.InputSource;
import org.xml.sax.SAXParseException;

/**
 * New-gen (Java 16+) object mapper: reads a pacs.008.001.08 business message (BusMsg with AppHdr and
 * Document, or a bare Document) into the immutable {@link Pacs008Message}. Elements are matched by
 * local name, so the ISO 20022 namespaces may or may not be present.
 */
public class Pacs008XmlMapper {

    private static final ErrorHandler STRICT = new ErrorHandler() {
        @Override
        public void warning(SAXParseException e) {
        }

        @Override
        public void error(SAXParseException e) throws SAXParseException {
            throw e;
        }

        @Override
        public void fatalError(SAXParseException e) throws SAXParseException {
            throw e;
        }
    };

    public Pacs008Message map(String xml) {
        var root = parse(xml).getDocumentElement();
        var document = "Document".equals(localName(root)) ? root : child(root, "Document");
        var transfer = child(document, "FIToFICstmrCdtTrf");
        if (transfer == null) {
            throw new MappingException("Document/FIToFICstmrCdtTrf is missing");
        }
        return new Pacs008Message(
                Optional.ofNullable(child(root, "AppHdr")).map(this::header).orElse(null),
                Optional.ofNullable(child(transfer, "GrpHdr")).map(this::groupHeader).orElse(null),
                children(transfer, "CdtTrfTxInf").stream().map(this::transaction).toList());
    }

    private Document parse(String xml) {
        try {
            var factory = DocumentBuilderFactory.newInstance();
            factory.setNamespaceAware(true);
            // Payment messages are untrusted input: no DTDs, no external entities.
            factory.setFeature("http://apache.org/xml/features/disallow-doctype-decl", true);
            factory.setFeature(XMLConstants.FEATURE_SECURE_PROCESSING, true);
            var builder = factory.newDocumentBuilder();
            builder.setErrorHandler(STRICT);
            return builder.parse(new InputSource(new StringReader(xml)));
        } catch (Exception e) {
            throw new MappingException("Not a well-formed XML message: " + e.getMessage(), e);
        }
    }

    private AppHeader header(Element e) {
        return new AppHeader(
                text(e, "Fr", "FIId", "FinInstnId", "BICFI"),
                text(e, "To", "FIId", "FinInstnId", "BICFI"),
                text(e, "BizMsgIdr"),
                text(e, "MsgDefIdr"),
                text(e, "BizSvc"),
                text(e, "CreDt"));
    }

    private GroupHeader groupHeader(Element e) {
        return new GroupHeader(
                text(e, "MsgId"),
                text(e, "CreDtTm"),
                text(e, "NbOfTxs"),
                text(e, "SttlmInf", "SttlmMtd"),
                text(e, "SttlmInf", "SttlmAcct", "Id", "Othr", "Id"));
    }

    private Transaction transaction(Element e) {
        var amount = child(e, "IntrBkSttlmAmt");
        return new Transaction(
                text(e, "PmtId", "InstrId"),
                text(e, "PmtId", "EndToEndId"),
                text(e, "PmtId", "UETR"),
                decimal(amount),
                attribute(amount, "Ccy"),
                text(e, "IntrBkSttlmDt"),
                text(e, "ChrgBr"),
                children(e, "ChrgsInf").stream().map(this::charge).toList(),
                text(e, "InstgAgt", "FinInstnId", "BICFI"),
                text(e, "InstdAgt", "FinInstnId", "BICFI"),
                text(e, "DbtrAgt", "FinInstnId", "BICFI"),
                text(e, "CdtrAgt", "FinInstnId", "BICFI"),
                party(child(e, "Dbtr")),
                account(child(e, "DbtrAcct")),
                party(child(e, "Cdtr")),
                account(child(e, "CdtrAcct")),
                children(child(e, "RmtInf"), "Ustrd").stream().map(u -> u.getTextContent().strip()).toList(),
                child(e, "RltdRmtInf") != null);
    }

    private Charge charge(Element e) {
        var amount = child(e, "Amt");
        return new Charge(decimal(amount), attribute(amount, "Ccy"), text(e, "Agt", "FinInstnId", "BICFI"));
    }

    private Party party(Element e) {
        if (e == null) {
            return null;
        }
        var address = Optional.ofNullable(child(e, "PstlAdr"))
                .map(a -> new PostalAddress(
                        text(a, "StrtNm"),
                        text(a, "BldgNb"),
                        text(a, "PstCd"),
                        text(a, "TwnNm"),
                        text(a, "Ctry"),
                        children(a, "AdrLine").stream().map(l -> l.getTextContent().strip()).toList()))
                .orElse(null);
        return new Party(text(e, "Nm"), text(e, "Id", "OrgId", "AnyBIC"), address);
    }

    private String account(Element e) {
        return Optional.ofNullable(text(e, "Id", "IBAN")).orElseGet(() -> text(e, "Id", "Othr", "Id"));
    }

    private static BigDecimal decimal(Element e) {
        if (e == null) {
            return null;
        }
        var value = e.getTextContent().strip();
        try {
            return new BigDecimal(value);
        } catch (NumberFormatException ex) {
            throw new MappingException("Not a decimal amount: " + value, ex);
        }
    }

    private static String attribute(Element e, String name) {
        return e != null && e.hasAttribute(name) ? e.getAttribute(name).strip() : null;
    }

    private static String text(Element start, String... path) {
        var e = start;
        for (var name : path) {
            e = child(e, name);
        }
        return Optional.ofNullable(e).map(Node::getTextContent).map(String::strip)
                .filter(s -> !s.isEmpty()).orElse(null);
    }

    private static Element child(Element parent, String name) {
        var found = children(parent, name);
        return found.isEmpty() ? null : found.get(0);
    }

    private static List<Element> children(Element parent, String name) {
        var result = new ArrayList<Element>();
        if (parent != null) {
            for (var n = parent.getFirstChild(); n != null; n = n.getNextSibling()) {
                if (n instanceof Element element && name.equals(localName(element))) {
                    result.add(element);
                }
            }
        }
        return result;
    }

    private static String localName(Node n) {
        return n.getLocalName() != null ? n.getLocalName() : n.getNodeName();
    }
}
