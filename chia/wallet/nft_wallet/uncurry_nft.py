from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional, Type, TypeVar

from blspy import G1Element

from chia.types.blockchain_format.program import Program
from chia.types.blockchain_format.sized_bytes import bytes32
from chia.util.ints import uint16
from chia.wallet.puzzles.load_clvm import load_clvm

log = logging.getLogger(__name__)
SINGLETON_TOP_LAYER_MOD = load_clvm("singleton_top_layer_v1_1.clvm")
NFT_MOD = load_clvm("nft_state_layer.clvm")
NFT_OWNERSHIP_LAYER = load_clvm("nft_ownership_layer.clvm")

_T_UncurriedNFT = TypeVar("_T_UncurriedNFT", bound="UncurriedNFT")


@dataclass(frozen=True)
class UncurriedNFT:
    """
    A simple solution for uncurry NFT puzzle.
    Initial the class with a full NFT puzzle, it will do a deep uncurry.
    This is the only place you need to change after modified the Chialisp curried parameters.
    """

    nft_mod_hash: Program
    """NFT module hash"""

    nft_state_layer: Program
    """NFT state layer puzzle"""

    singleton_struct: Program
    """
    Singleton struct
    [singleton_mod_hash, singleton_launcher_id, launcher_puzhash]
    """
    singleton_mod_hash: Program
    singleton_launcher_id: Program
    launcher_puzhash: Program

    metadata_updater_hash: Program
    """Metadata updater puzzle hash"""

    metadata: Program
    """
    NFT metadata
    [("u", data_uris), ("h", data_hash)]
    """
    data_uris: Program
    data_hash: Program
    meta_uris: Program
    meta_hash: Program
    license_uris: Program
    license_hash: Program
    series_number: Program
    series_total: Program

    inner_puzzle: Program
    """NFT state layer inner puzzle"""

    p2_puzzle: Program
    """p2 puzzle of the owner, either for ownership layer or standard"""
    # ownership layer fields
    owner_did: Optional[Program]
    """Owner's DID"""
    owner_pubkey: Optional[G1Element]
    nft_inner_puzzle_hash: Optional[bytes32]
    """Puzzle hash of the ownership layer inner puzzle """

    transfer_program_hash: Optional[bytes32]
    """Puzzle hash of the transfer program"""

    transfer_program_curry_params: Optional[Program]
    """
    Curried parameters of the transfer program
    [royalty_address, trade_price_percentage, settlement_mod_hash, cat_mod_hash]
    """
    royalty_address: Optional[bytes32]
    trade_price_percentage: Optional[uint16]

    @classmethod
    def uncurry(cls: Type[_T_UncurriedNFT], puzzle: Program) -> UncurriedNFT:
        """
        Try to uncurry a NFT puzzle
        :param cls UncurriedNFT class
        :param puzzle: Puzzle program
        :return Uncurried NFT
        """
        mod, curried_args = puzzle.uncurry()
        if mod != SINGLETON_TOP_LAYER_MOD:
            raise ValueError(f"Cannot uncurry NFT puzzle, failed on singleton top layer: Mod {mod}")
        try:
            (singleton_struct, nft_state_layer) = curried_args.as_iter()
            singleton_mod_hash = singleton_struct.first()
            singleton_launcher_id = singleton_struct.rest().first()
            launcher_puzhash = singleton_struct.rest().rest()
        except ValueError as e:
            raise ValueError(f"Cannot uncurry singleton top layer: Args {curried_args}") from e

        mod, curried_args = curried_args.rest().first().uncurry()
        if mod != NFT_MOD:
            raise ValueError(f"Cannot uncurry NFT puzzle, failed on NFT state layer: Mod {mod}")
        try:
            # Set nft parameters

            (nft_mod_hash, metadata, metadata_updater_hash, inner_puzzle) = curried_args.as_iter()
            data_uris = Program.to([])
            data_hash = Program.to(0)
            meta_uris = Program.to([])
            meta_hash = Program.to(0)
            license_uris = Program.to([])
            license_hash = Program.to(0)
            series_number = Program.to(1)
            series_total = Program.to(1)
            # Set metadata
            for kv_pair in metadata.as_iter():
                if kv_pair.first().as_atom() == b"u":
                    data_uris = kv_pair.rest()
                if kv_pair.first().as_atom() == b"h":
                    data_hash = kv_pair.rest()
                if kv_pair.first().as_atom() == b"mu":
                    meta_uris = kv_pair.rest()
                if kv_pair.first().as_atom() == b"mh":
                    meta_hash = kv_pair.rest()
                if kv_pair.first().as_atom() == b"lu":
                    license_uris = kv_pair.rest()
                if kv_pair.first().as_atom() == b"lh":
                    license_hash = kv_pair.rest()
                if kv_pair.first().as_atom() == b"sn":
                    series_number = kv_pair.rest()
                if kv_pair.first().as_atom() == b"st":
                    series_total = kv_pair.rest()
            current_did = None
            pubkey = None
            transfer_program_mod = None
            transfer_program_args = None
            royalty_address = None
            royalty_percentage = None
            nft_inner_puzzle_mod = None
            mod_hash, ol_args = inner_puzzle.uncurry()
            if mod_hash == NFT_OWNERSHIP_LAYER.get_tree_hash():
                current_did, transfer_program, nft_inner_puzzle = ol_args
                transfer_program_mod, transfer_program_args = transfer_program.uncurry()
                nft_inner_puzzle_mod, nft_inner_puzzle_args = nft_inner_puzzle.uncurry()
                _, royalty_address, royalty_percentage, _, _ = transfer_program_args
                _, _, p2_puzzle = nft_inner_puzzle_args
            else:
                p2_puzzle = inner_puzzle
        except Exception as e:
            raise ValueError(f"Cannot uncurry NFT state layer: Args {curried_args}") from e
        return cls(
            nft_mod_hash=nft_mod_hash,
            nft_state_layer=nft_state_layer,
            singleton_struct=singleton_struct,
            singleton_mod_hash=singleton_mod_hash,
            singleton_launcher_id=singleton_launcher_id,
            launcher_puzhash=launcher_puzhash,
            metadata=metadata,
            data_uris=data_uris,
            data_hash=data_hash,
            p2_puzzle=p2_puzzle,
            metadata_updater_hash=metadata_updater_hash,
            meta_uris=meta_uris,
            meta_hash=meta_hash,
            license_uris=license_uris,
            license_hash=license_hash,
            series_number=series_number,
            series_total=series_total,
            inner_puzzle=inner_puzzle,
            # TODO: Set/Remove following fields after NFT1 implemented
            owner_did=current_did,
            owner_pubkey=pubkey,
            transfer_program_hash=transfer_program_mod,
            transfer_program_curry_params=transfer_program_args,
            royalty_address=royalty_address,
            trade_price_percentage=royalty_percentage,
            nft_inner_puzzle_hash=nft_inner_puzzle_mod,
        )
