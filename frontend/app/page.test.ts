import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import Home from "./page";

describe("Home", () => {
  it("renders the political context workspace", () => {
    const html = renderToStaticMarkup(React.createElement(Home));

    expect(html).toContain("Politik Yuk");
    expect(html).toContain("Understand political news with sources, uncertainty, and context");
    expect(html).toContain("Topic, question, headline, pasted claim, or social text");
    expect(html).toContain("Explain with sources");
    expect(html).toContain("Screenshot text is treated as an unverified claim");
  });
});
