import * as React from "react";
import { useAuth0 } from "@auth0/auth0-react";
import { Button } from "@/components/ui/button";

type MarimoDocument = { filename: string };

const API_BASE = "http://localhost:9000";

async function authFetch(
  url: string,
  getToken: () => Promise<string>,
  init: RequestInit = {}
) {
  const token = await getToken();
  return fetch(url, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
      ...(init.headers || {}),
    },
  });
}

export default function Dashboard() {
  const { user, logout, getAccessTokenSilently } = useAuth0();
  const [docs, setDocs] = React.useState<MarimoDocument[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);

  const getToken = React.useCallback(() => {
    // same audience/scope you set in <Auth0Provider>
    return getAccessTokenSilently({
      authorizationParams: {
        audience: "https://dev-mtmjc4rwzjq4eryf.us.auth0.com/api/v2/",
        scope: "read:current_user",
      },
    });
  }, [getAccessTokenSilently]);

  const refresh = React.useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await authFetch(`${API_BASE}/documents`, getToken);
      if (!res.ok) throw new Error(`Failed to load documents (${res.status})`);
      const filenames: string[] = await res.json();
      setDocs(filenames.map((f) => ({ filename: f })));
    } catch (e: any) {
      setError(e?.message ?? "Failed to load documents");
    } finally {
      setLoading(false);
    }
  }, [getToken]);

  React.useEffect(() => {
    refresh();
  }, [refresh]);

  const createDoc = async () => {
    const name = prompt("New document name (without .py):");
    if (!name) return;
    const body = JSON.stringify({ document_name: `${name}.py` });
    const res = await authFetch(`${API_BASE}/documents`, getToken, {
      method: "POST",
      body,
    });
    if (!res.ok) return alert("Failed to create document");
    await refresh();
  };

  const deleteDoc = async (filename: string) => {
    if (!confirm(`Delete ${filename}?`)) return;
    const body = JSON.stringify({ document_name: filename });
    const res = await authFetch(`${API_BASE}/documents`, getToken, {
      method: "DELETE",
      body,
    });
    if (!res.ok) return alert("Failed to delete document");
    await refresh();
  };

  const openDoc = async (filename: string) => {
    const res = await authFetch(`${API_BASE}/spawn`, getToken, {
      method: "POST",
      body: JSON.stringify({ document_name: filename }),
    });
    if (!res.ok) return alert("Failed to open document");
    const data = await res.json();
    if (data.redirect) window.open(data.redirect, "_blank");
  };

  return (
    <div className="mx-auto max-w-3xl p-6 space-y-6">
      {/* Header */}
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Marimo Dashboard</h1>
          <p className="text-sm text-muted-foreground">
            Welcome, {user?.name || user?.email || "User"}
          </p>
        </div>
        <div className="space-x-2">
          <Button variant="outline" onClick={createDoc}>New Document</Button>
          <Button
            variant="secondary"
            onClick={() => logout({ logoutParams: { returnTo: window.location.origin } })}
          >
            Logout
          </Button>
        </div>
      </header>

      {/* Content */}
      {loading && <p className="text-muted-foreground">Loading…</p>}
      {error && <p className="text-red-500">{error}</p>}

      {!loading && !error && (
        <div className="rounded-md border">
          {docs.length === 0 ? (
            <div className="p-6 text-center text-muted-foreground">
              No documents yet. Create your first one!
            </div>
          ) : (
            <ul className="divide-y">
              {docs.map((d) => (
                <li key={d.filename} className="flex items-center justify-between p-4">
                  <div className="truncate">
                    <div className="font-medium">{d.filename.replace(".py", "")}</div>
                    <div className="text-xs text-muted-foreground">{d.filename}</div>
                  </div>
                  <div className="shrink-0 space-x-2">
                    <Button variant="outline" onClick={() => openDoc(d.filename)}>Open</Button>
                    <Button variant="destructive" onClick={() => deleteDoc(d.filename)}>Delete</Button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
