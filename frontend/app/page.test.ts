import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import Home from "./page";

describe("Home", () => {
  it("renders the political context workspace", () => {
    const html = renderToStaticMarkup(React.createElement(Home));

    expect(html).toContain("Understand Indonesian political news with evidence in view.");
    expect(html).toContain("Topic, question, headline, URL, or pasted claim");
    expect(html).toContain("Explain with sources");
  });
});
