// https://auth0.com/docs/quickstart/spa/react/02-calling-an-api#set-up-the-auth0-service
import React from "react";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { useAuth0 } from "@auth0/auth0-react";


export default function CardDemo() {

  const { user, isAuthenticated, isLoading,loginWithRedirect,getAccessTokenSilently } = useAuth0();
  const [userMetadata, setUserMetadata] = useState(null);

  useEffect(() => {
  const getUserMetadata = async () => {
    // If the user or user.sub is not available yet, skip fetching metadata.
    if (!user?.sub) return;
    const env_domain = import.meta.env.VITE_AUTH0_DOMAIN as string;
    const domain = env_domain;

    try {
      const accessToken = await getAccessTokenSilently({
        authorizationParams: {
          audience: `https://${domain}/api/v2/`,
          scope: "read:current_user",
        },
      });
      const userDetailsByIdUrl = `https://${domain}/api/v2/users/${user.sub}`;

      const metadataResponse = await fetch(userDetailsByIdUrl, {
        headers: {
          Authorization: `Bearer ${accessToken}`,
        },
      });

      const { user_metadata } = await metadataResponse.json();

      setUserMetadata(user_metadata);
    } catch (e) {
      if (e instanceof Error){
        console.log(e.message);
      }
      }
    };

    getUserMetadata();
    }, [getAccessTokenSilently, user?.sub]);
  const handleLogin = async () => {
    try {
      await loginWithRedirect({
        appState: {
          returnTo: "/dashboard", // redirect here after Auth0 login
        },
      });
    } catch (error) {
      console.error("Login failed:", error);
    }
  };
  return (
    <Card className="w-full max-w-sm">
      <CardHeader>
        <CardTitle>Login to your Marimo JupyterHub</CardTitle>
        <CardDescription>
          Enter your email below to access your account
        </CardDescription>
      </CardHeader>

      <CardContent>
        {/* These inputs are purely cosmetic unless you implement a custom DB login.
            Auth0 Hosted Login will handle credentials on the redirect screen. */}
        <form>
          <div className="flex flex-col gap-6">
            <div className="grid gap-2">
              <label htmlFor="email" className="text-sm font-medium">
                Email
              </label>
              <input
                id="email"
                type="email"
                placeholder="m@example.com"
                className="w-full px-3 py-2 border rounded-md"
                required
              />
            </div>
            <div className="grid gap-2">
              <div className="flex items-center">
                <label htmlFor="password" className="text-sm font-medium">
                  Password
                </label>
                <a
                  href="#"
                  className="ml-auto inline-block text-sm underline-offset-4 hover:underline"
                >
                  Forgot your password?
                </a>
              </div>
              <input
                id="password"
                type="password"
                className="w-full px-3 py-2 border rounded-md"
                required
              />
            </div>
          </div>
        </form>
      </CardContent>

      <CardFooter className="flex-col gap-2">
        <Button
          className="w-full"
          type="button"
          onClick={handleLogin}
          disabled={isLoading}
        >
          {isLoading ? "Redirecting..." : "Login with Auth0"}
        </Button>

        <div className="text-xs text-muted-foreground mt-2 text-center">
          You will be redirected to Auth0 for authentication
        </div>
      </CardFooter>
    </Card>
  );
}
