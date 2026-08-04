import { useEffect } from "react";
import { useLocation } from "react-router-dom";

import { buildLoginRedirect } from "../../libs/routes";

function RequireAuth({ children, context }) {
  const location = useLocation();
  const isAuthenticated = Boolean(context?.user?.isAuthenticated);
  const loginRedirect = buildLoginRedirect(
    context?.urls,
    location.pathname,
    location.search,
    location.hash
  );

  useEffect(() => {
    if (isAuthenticated) {
      return;
    }

    window.location.assign(loginRedirect);
  }, [isAuthenticated, loginRedirect]);

  if (isAuthenticated) {
    return children;
  }

  return (
    <section className="container py-5 mt-5">
      <div className="alert alert-warning mt-5" role="alert">
        Redirecting to login… If you are not redirected automatically,
        {" "}
        continue to the <a href={loginRedirect}>sign-in page</a>.
      </div>
    </section>
  );
}

export default RequireAuth;
