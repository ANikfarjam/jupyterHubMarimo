// request_methods.tsx
import {
  createClient,
  createConfig,
  type OptionsLegacyParser,
} from "@hey-api/client-axios";
import { createDocument, spawnResponse,DocumentInfo, ListDocumentsResponse,GetDocumentResponse  } from "./types";

export const client = createClient(createConfig());

// For spawning user server
export const spawnServer = <ThrowOnError extends boolean = false>(
    options: OptionsLegacyParser<spawnResponse, ThrowOnError> & {
        userToken: string;
    }
) => {
    // Pull out fields we don't want sent as part of the axios request config
    const { client: optClient, userToken, ...rest } = options as any;

        const usedClient = (optClient ?? client) as any;

        const headers = {
            ...(rest.headers ?? {}),
            Authorization: `Bearer ${userToken}`,
        };

            return usedClient.post({
            ...rest,
            url: "http://localhost:8000/spawn",
            headers,
        });
};

// For creating documents (uses /documents endpoint with Form data)
export const createJhubDocument = <ThrowOnError extends boolean = false>(
    options: OptionsLegacyParser<any, ThrowOnError> & {
        userToken: string;
        documentName: string;
    }
) => {
    const { client: optClient, userToken, documentName, ...rest } = options as any;

    const formData = new FormData();
    formData.append("document_name", documentName);

    // Build headers but don't override Content-Type when using FormData; the browser sets it
        const providedHeaders = rest.headers ?? {};
        // Make a shallow copy and ensure Content-Type is removed so browser sets it for FormData
        const headersCopy: Record<string, unknown> = { ...providedHeaders };
        delete (headersCopy as any)["Content-Type"];
        const headers = {
            ...headersCopy,
            Authorization: `Bearer ${userToken}`,
        };

        const usedClient = (optClient ?? client) as any;

            return usedClient.post({
            ...rest,
            url: "http://localhost:8000/documents",
            headers,
            data: formData,
        });
};

// For listing all documents
export const listDocuments = <ThrowOnError extends boolean = false>(
    options: OptionsLegacyParser<ListDocumentsResponse, ThrowOnError> & {
        userToken: string;
    }
) => {
    const { client: optClient, userToken, ...rest } = options as any;

    const usedClient = (optClient ?? client) as any;

    const headers = {
        ...(rest.headers ?? {}),
        Authorization: `Bearer ${userToken}`,
    };

    return usedClient.get({
        ...rest,
        url: "http://localhost:8000/documents",
        headers,
    });
};

// For getting a specific document
export const getDocument = <ThrowOnError extends boolean = false>(
    options: OptionsLegacyParser<GetDocumentResponse, ThrowOnError> & {
        userToken: string;
        documentName: string;
    }
) => {
    const { client: optClient, userToken, documentName, ...rest } = options as any;

    const usedClient = (optClient ?? client) as any;

    const headers = {
        ...(rest.headers ?? {}),
        Authorization: `Bearer ${userToken}`,
    };

    return usedClient.get({
        ...rest,
        url: `http://localhost:8000/documents/${encodeURIComponent(documentName)}`,
        headers,
    });
};