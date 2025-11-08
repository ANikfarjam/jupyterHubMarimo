// request_methods.tsx
import {
  createClient,
  createConfig,
  type OptionsLegacyParser,
} from "@hey-api/client-axios";
// Note: specific response types live in `./types` but are not required in this module
// because request helper functions keep response typing separate from request options.

export const client = createClient(createConfig(
  {baseURL: "http://localhost:9000"},
));

// JupyterHub URL where marimo servers run (different from API service)
export const JUPYTERHUB_URL = "http://localhost:8000";

// Base request options for client calls (do NOT mix in response shape)
// Keep this independent from the response generic so callers can pass only
// request-related properties (headers, params, etc.) plus `userToken`.
type BaseRequestOptions = Omit<OptionsLegacyParser<any, false>, "url"> & {
    userToken: string;
};

// For spawning user server
export const spawnServer = (
    options: BaseRequestOptions
) => {
    const { client: optClient, userToken, ...rest } = options as any;
    const usedClient = (optClient ?? client) as any;

    const headers = {
        ...(rest.headers ?? {}),
        Authorization: `Bearer ${userToken}`,
    };

    return usedClient.post({
        ...rest,
        url: "/spawn",
        headers,
    });
};

// For creating documents (uses /documents endpoint with query parameter)
export const createJhubDocument = (
    options: BaseRequestOptions & {
        documentName: string;
    }
) => {
    const { client: optClient, userToken, documentName, ...rest } = options as any;
    const usedClient = (optClient ?? client) as any;

    console.log("Making CREATE DOCUMENT request to: http://localhost:9000/documents");
    console.log("Document name:", documentName);

    const headers = {
        ...(rest.headers ?? {}),
        Authorization: `Bearer ${userToken}`,
    };

    console.log("Headers:", headers);

    // Encode the document name and append to URL as query parameter
    const url = `/documents?document_name=${encodeURIComponent(documentName)}`;

    return usedClient.post({
        ...rest,
        url,
        headers,
    });
};


// For listing all documents
export const listDocuments = (
    options: BaseRequestOptions
) => {
    const { client: optClient, userToken, ...rest } = options as any;
    const usedClient = (optClient ?? client) as any;

    const headers = {
        ...(rest.headers ?? {}),
        Authorization: `Bearer ${userToken}`,
    };

    return usedClient.get({
        ...rest,
        url: "/documents",
        headers,
    });
};

// For getting a specific document
export const getDocument = (
    options: BaseRequestOptions & {
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
        url: `/documents/${encodeURIComponent(documentName)}`,
        headers,
    });
};

// Add delete document method for completeness
export const deleteDocument = (
    options: BaseRequestOptions & {
        documentName: string;
    }
) => {
    const { client: optClient, userToken, documentName, ...rest } = options as any;
    const usedClient = (optClient ?? client) as any;

    const headers = {
        ...(rest.headers ?? {}),
        Authorization: `Bearer ${userToken}`,
    };

    return usedClient.delete({
        ...rest,
        url: `/documents/${encodeURIComponent(documentName)}`,
        headers,
    });
};


// Get all servers for authenticated user
export const getMyServers = (
  options: BaseRequestOptions
) => {
  const { client: optClient, userToken, ...rest } = options as any;
  const usedClient = (optClient ?? client) as any;

  const headers = {
    ...(rest.headers ?? {}),
    Authorization: `Bearer ${userToken}`,
  };

  return usedClient.get({
    ...rest,
    url: "/my-servers",
    headers,
  });
};

// Check server status for authenticated user
export const checkMyServersStatus = (
  options: BaseRequestOptions
) => {
  const { client: optClient, userToken, ...rest } = options as any;
  const usedClient = (optClient ?? client) as any;

  const headers = {
    ...(rest.headers ?? {}),
    Authorization: `Bearer ${userToken}`,
  };

  return usedClient.get({
    ...rest,
    url: "/my-servers/status",
    headers,
  });
};

// Admin endpoints (require HUB_API_TOKEN)
export const getUserServers = (
  options: BaseRequestOptions & {
    username: string;
  }
) => {
  const { client: optClient, userToken, username, ...rest } = options as any;
  const usedClient = (optClient ?? client) as any;

  const headers = {
    ...(rest.headers ?? {}),
    "X-API-Token": userToken, // Using HUB_API_TOKEN for admin endpoints
  };

  return usedClient.get({
    ...rest,
    url: `/users/${encodeURIComponent(username)}/servers`,
    headers,
  });
};

export const getUserServerStatus = (
  options: BaseRequestOptions & {
    username: string;
    serverName: string;
  }
) => {
  const { client: optClient, userToken, username, serverName, ...rest } = options as any;
  const usedClient = (optClient ?? client) as any;

  const headers = {
    ...(rest.headers ?? {}),
    "X-API-Token": userToken, // Using HUB_API_TOKEN for admin endpoints
  };

  return usedClient.get({
    ...rest,
    url: `/users/${encodeURIComponent(username)}/servers/${encodeURIComponent(serverName)}`,
    headers,
  });
};