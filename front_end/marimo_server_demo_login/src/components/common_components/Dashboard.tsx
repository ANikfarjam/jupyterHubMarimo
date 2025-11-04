import * as React from "react";
import { useState, useEffect, useCallback } from "react";
import { useAuth0 } from "@auth0/auth0-react";
import { Button } from "@/components/ui/button";
import {
  spawnServer,
  createJhubDocument,
  listDocuments,
  deleteDocument,
  getMyServers,
  getUserServerStatus,
} from '../../../api/request_methods'

import {
  Table,
  TableHeader,
  TableBody,
  TableFooter,
  TableHead,
  TableRow,
  TableCell,
  TableCaption,
}from "@/components/ui/table";
import ServersDataTable from "./DataTable";

type MarimoDocument = { filename: string };
// Shape returned by the listDocuments API
type JupyterDocument = { name: string };
type ServersList = string[];
export default function Dashboard() {
  const { user ,logout, getAccessTokenSilently, loginWithRedirect } = useAuth0();
  const [docs, setDocs] = useState<MarimoDocument[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [ spawnedServers, setSpawnedServers ] = useState< ServersList | null>(null);
  
  
  const getToken = useCallback(async () => {
    try {
      return await getAccessTokenSilently().catch(async (error) => {
        if (error.error === 'missing_refresh_token' || error.error === 'consent_required') {
          // Force re-authentication
          await loginWithRedirect({
            authorizationParams: {
              audience: "https://dev-mtmjc4rwzjq4eryf.us.auth0.com/api/v2/",
              scope: "read:current_user openid profile email",
            },
          });
        }
        throw error;
      });
    } catch (error: any) {
      console.error("Token error:", error);
      if (error.error === 'consent_required' || error.error === 'missing_refresh_token') {
        await loginWithRedirect({
          authorizationParams: {
            audience: "https://dev-mtmjc4rwzjq4eryf.us.auth0.com/api/v2/",
            scope: "read:current_user openid profile email",
          },
        });
      }
      throw error;
    }
  }, [getAccessTokenSilently, loginWithRedirect]);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const token = await getToken();
      const response = await listDocuments({
        userToken: token,
      });
      
      if (response.data.ok) {
        const documents = response.data.documents.map((doc: JupyterDocument) => ({
          filename: doc.name
        }));
        setDocs(documents);
      } else {
        setError(response.data.message || "Failed to load documents");
      }
    } catch (e: any) {
      console.error("Refresh error:", e);
      
      // Handle specific Auth0 errors
      if (e.error === 'missing_refresh_token' || e.error === 'consent_required') {
        setError("Authentication session expired. Please log in again.");
        // Optionally trigger re-login
        await loginWithRedirect({
          authorizationParams: {
            audience: "https://dev-mtmjc4rwzjq4eryf.us.auth0.com/api/v2/",
            scope: "read:current_user openid profile email",
          },
        });
      } else {
        setError(e?.message ?? "Failed to load documents");
      }
    } finally {
      setLoading(false);
    }
  }, [getToken, loginWithRedirect]);

  React.useEffect(() => {
    refresh();
  }, [refresh]);


  const createDoc = async () => {
    const name = prompt("New document name (without .py):");
    if (!name) return;
    
    try {
      const token = await getToken();
      const response = await createJhubDocument({
        userToken: token,
        documentName: `${name}`,
      });
      
      if (response.data.ok) {
        await refresh();
      } else {
        alert("Failed to create document");
      }
    } catch (error) {
      alert("Failed to create document");
    }
  };

  const deleteDoc = async (filename: string) => {
    if (!confirm(`Delete ${filename}?`)) return;
    
    try {
      const token = await getToken();
      const response = await deleteDocument({
        userToken: token,
        documentName: filename,
      });
      
      if (response.data.ok) {
        await refresh();
      } else {
        alert("Failed to delete document");
      }
    } catch (error) {
      alert("Failed to delete document");
    }
  };



 
  const handleSpawn = async () => {
    try {
      const token = await getToken();

      // Now we just send the token, no document name needed
      const res = await spawnServer({
        userToken: token,
        // No data payload needed - backend extracts username from token
      });

      if (res.data?.ok) {
        console.log("Spawn success:", res.data);
        
        if (res.data.server_ready) {
          // Redirect to the server
          alert(`Server spawned successfully for user: ${res.data.user}`);
          window.location.href = res.data.nextUrl;
        } else {
          alert(`Server is starting for user: ${res.data.user}. Please wait a moment and try creating documents.`);
        }
      } else {
        console.error("Spawn failed:", res.data?.message);
        alert(`Failed to spawn server: ${res.data?.message || 'Unknown error'}`);
      }

    } catch (error: any) {
      console.error("Spawn failed:", error);
      
      if (error.response?.status === 401) {
        alert("Authentication failed. Please log in again.");
        await loginWithRedirect({
          authorizationParams: {
            audience: "https://dev-mtmjc4rwzjq4eryf.us.auth0.com/api/v2/",
            scope: "read:current_user openid profile email",
          },
        });
      } else {
        alert(`Failed to spawn server: ${error?.message || 'Unknown error'}`);
      }
    }
  };


  const listSpawnServers = async (): Promise<ServersList> => {
    try {
      const token = await getToken();
      const res = await getMyServers({ userToken: token });

      if (res.data?.ok && res.data?.url) {
        const servers: ServersList = [res.data.url];
        console.log("added servers:", servers);
        return servers;
      }

      console.log("There are no servers created for this user!");
      return [];
    } catch (e) {
      console.error(e);
      return [];
    }
    };

    useEffect(() => {
      const fetchData = async () => {
        const spawnList = await listSpawnServers();
        setSpawnedServers(spawnList);
      };

      fetchData();
    }, []);



  return (
    <div className="mx-auto max-w-3xl p-6 space-y-6">
      {/* Header */}
      <header>
        <div>
          <h1 className="text-2xl font-bold justify-start">Marimo Dashboard</h1>
          <p className="text-sm text-muted-foreground">
            Welcome, {user?.name || user?.email || "User"}
          </p>
        </div>
        <div className="space-x-2">
          <Button variant="outline" onClick={handleSpawn}>New Server</Button>
          <Button variant="outline" onClick={createDoc}>New Document</Button>
          <Button
            variant="secondary"
            onClick={() => logout({ logoutParams: { returnTo: window.location.origin } })}
          >
            Logout
          </Button>
        </div>
      </header>
      <div>
        <ServersDataTable></ServersDataTable>
      </div>

    </div>
  );
}