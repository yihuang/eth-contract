{
  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/25.05";
    utils.url = "github:numtide/flake-utils";
    foundry.url = "github:shazow/foundry.nix/stable"; # Use stable branch for permanent releases
  };

  outputs =
    {
      self,
      nixpkgs,
      utils,
      foundry,
    }:
    utils.lib.eachDefaultSystem (
      system:
      let
        pkgs = import nixpkgs {
          inherit system;
          overlays = [ foundry.overlay ];
        };
      in
      {

        devShell =
          with pkgs;
          mkShell {
            buildInputs = [
              python312Full
              uv
              foundry-bin
            ];
          };
      }
    );
}
