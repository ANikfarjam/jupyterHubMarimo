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
  checkMyServersStatus,
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
import { DocumentsDataTable } from "./DataTable";

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
        documentName: name, 
      });
      
      // Fix the response checking - handle both success and error cases properly
      if (response && response.data && response.data.ok) {
        await refresh();
        alert("Document created successfully!");
      } else {
        const errorMessage = response?.data?.message || "Unknown error";
        alert("Failed to create document: " + errorMessage);
      }
    } catch (error: any) {
      console.error("Create document error:", error);
      
      // Handle different error scenarios
      if (error.response) {
        // Server responded with error status
        const errorMessage = error.response.data?.detail || error.response.data?.message || "Server error";
        alert("Failed to create document: " + errorMessage);
      } else if (error.request) {
        // Request was made but no response received
        alert("Failed to create document: No response from server");
      } else {
        // Something else happened
        alert("Failed to create document: " + (error?.message || "Unknown error"));
      }
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
        const username = res.data.user;

        if (res.data.server_ready) {
          // Redirect to the server
          alert(`Server spawned successfully for user: ${username}`);
          window.location.href = res.data.nextUrl;
        } else {
          // Server is starting, poll for status
          alert(`Server is starting for user: ${username}. Please wait...`);

          // Poll server status every 3 seconds
          const pollInterval = setInterval(async () => {
            try {
              const statusRes = await checkMyServersStatus({
                userToken: token,
              });

              console.log("Polling server status:", statusRes.data);

              if (statusRes.data?.ok && statusRes.data?.has_running_servers) {
                clearInterval(pollInterval);
                alert(`Server is now ready for user: ${username}!`);

                // Get the server URL from running servers
                const serverUrl = statusRes.data.running_servers?.[0]?.url || `/hub/user/${username}/`;
                window.location.href = serverUrl;
              }
            } catch (pollError) {
              console.error("Error polling server status:", pollError);
            }
          }, 3000);

          // Stop polling after 2 minutes (timeout)
          setTimeout(() => {
            clearInterval(pollInterval);
            console.log("Server spawn timeout - stopped polling");
          }, 120000);
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
        <h1>Servers</h1>
        <ServersDataTable></ServersDataTable>
      </div>
      <div>
        <h1>Documents</h1>
        <DocumentsDataTable></DocumentsDataTable>
      </div>

    </div>
  );
}