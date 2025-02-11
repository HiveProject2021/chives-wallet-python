import json
import time
import asyncio
import aiosqlite
import sqlite3
import logging
import redis

from typing import Dict, List, Optional

from blspy import AugSchemeMPL, G2Element, PrivateKey

from chia.consensus.constants import ConsensusConstants
from chia.util.hash import std_hash
from chia.types.announcement import Announcement
from chia.types.blockchain_format.coin import Coin
from chia.types.blockchain_format.program import Program
from chia.types.blockchain_format.sized_bytes import bytes32
from chia.types.coin_spend import CoinSpend
from chia.types.condition_opcodes import ConditionOpcode
from chia.types.condition_with_args import ConditionWithArgs
from chia.types.spend_bundle import SpendBundle
from clvm.casts import int_from_bytes, int_to_bytes
from chia.util.condition_tools import conditions_by_opcode, conditions_for_solution, pkm_pairs_for_conditions_dict
from chia.util.ints import uint32, uint64
from chia.util.byte_types import hexstr_to_bytes


from chia.types.blockchain_format.classgroup import ClassgroupElement
from chia.types.blockchain_format.coin import Coin
from chia.types.blockchain_format.foliage import TransactionsInfo
from chia.types.blockchain_format.program import SerializedProgram
from chia.types.blockchain_format.sized_bytes import bytes32
from chia.types.blockchain_format.slots import InfusedChallengeChainSubSlot
from chia.types.blockchain_format.vdf import VDFInfo, VDFProof
from chia.types.end_of_slot_bundle import EndOfSubSlotBundle
from chia.types.full_block import FullBlock
from chia.types.unfinished_block import UnfinishedBlock

from chia.wallet.derive_keys import master_sk_to_wallet_sk
from chia.wallet.puzzles.p2_delegated_puzzle_or_hidden_puzzle import (
    DEFAULT_HIDDEN_PUZZLE_HASH,
    calculate_synthetic_secret_key,
    puzzle_for_pk,
    solution_for_conditions,
)
from chia.wallet.puzzles.puzzle_utils import (
    make_assert_aggsig_condition,
    make_assert_coin_announcement,
    make_assert_puzzle_announcement,
    make_assert_relative_height_exceeds_condition,
    make_assert_absolute_height_exceeds_condition,
    make_assert_my_coin_id_condition,
    make_assert_absolute_seconds_exceeds_condition,
    make_assert_relative_seconds_exceeds_condition,
    make_create_coin_announcement,
    make_create_puzzle_announcement,
    make_create_coin_condition,
    make_reserve_fee_condition,
    make_assert_my_parent_id,
    make_assert_my_puzzlehash,
    make_assert_my_amount,
)
from chia.util.keychain import Keychain, bytes_from_mnemonic, bytes_to_mnemonic, generate_mnemonic, mnemonic_to_seed

from chia.consensus.default_constants import DEFAULT_CONSTANTS

from chia.rpc.full_node_rpc_api import FullNodeRpcApi
from chia.rpc.full_node_rpc_client import FullNodeRpcClient
from chia.util.default_root import DEFAULT_ROOT_PATH
from chia.util.config import load_config
from chia.util.ints import uint16
from chia.util.misc import format_bytes
from pathlib import Path

from chia.wallet.derive_keys import master_sk_to_wallet_sk,master_sk_to_wallet_sk_unhardened


class WalletTool:
    next_address = 0
    pubkey_num_lookup: Dict[bytes, uint32] = {}

    def __init__(self, constants: ConsensusConstants, sk: Optional[PrivateKey] = None):
        
        
        self.constants = constants
        self.current_balance = 0
        self.my_utxos: set = set()
        self.generator_lookups: Dict = {}
        self.puzzle_pk_cache: Dict = {}
        
        #print(constants)
        #print()
        #print()
        #print()
     
    async def  push_transaction(self):  
        pool = redis.ConnectionPool(host='localhost', port=6379, db=0)
        r = redis.Redis(connection_pool=pool)
        #mnemonic = generate_mnemonic()
        #when you want to make a send transaction, you must need a account.
        #here it is to fill the mnemonic works and to make a account
        mnemonic = ""
        entropy = bytes_from_mnemonic(mnemonic)
        seed = mnemonic_to_seed(mnemonic, "")
        self.private_key = AugSchemeMPL.key_gen(seed)
        fingerprint = self.private_key.get_g1().get_fingerprint()
        
        #得到指定账户的300个地址.
        AllPuzzleHashArray = []
        for i in range(0, 10):
            pubkey = master_sk_to_wallet_sk(self.private_key, i).get_g1()
            puzzle = puzzle_for_pk(bytes(pubkey))
            puzzle_hash = str(puzzle.get_tree_hash())
            AllPuzzleHashArray.append(puzzle_hash);
            #print(puzzle_hash)
        '''
        for i in range(0, 10):
            pubkey = master_sk_to_wallet_sk_unhardened(self.private_key, i).get_g1()
            puzzle = puzzle_for_pk(bytes(pubkey))
            puzzle_hash = str(puzzle.get_tree_hash())
            AllPuzzleHashArray.append(puzzle_hash);
        '''    
        #print(AllPuzzleHashArray)
        #构建一个这样的结构: 'PuzzleHash','PuzzleHash','PuzzleHash','PuzzleHash','PuzzleHash'
        separator = "','"
        AllPuzzleHashArrayText = separator.join(AllPuzzleHashArray)
        AllPuzzleHashArrayText = "'"+AllPuzzleHashArrayText+"'"
        #print(AllPuzzleHashArrayText)
        
        #连接数据库
        root_path = DEFAULT_ROOT_PATH
        config = load_config(root_path, "config.yaml")
        selected = config["selected_network"]
        prefix = config["network_overrides"]["config"][selected]["address_prefix"]
        log = logging.Logger
        #db_connection = await aiosqlite.connect("/home/ubuntu/.chia/mainnet/db/blockchain_v2_testnet10.sqlite")
        db_connection = await aiosqlite.connect("/home/wang/.chia/mainnet/db/blockchain_v2_testnet10.sqlite")
        
        #手工输入来构建参数部分代码
        SendToAmount        = uint64(11)
        fee                 = uint64(0)
        SendToPuzzleHash    = "04cef8e607b69bea527f1de60b2ce9789352c94e2c36aa395d80d3bb99247bae"
        #coin = Coin(hexstr_to_bytes("944462ee5b59b8128e90b9a650f865c10000000000000000000000000005ce5d"), hexstr_to_bytes("68dffc83153d9f68f3fe89f5cf982149c7ca0f60369124a5b06a52f5a0d2ab81"), uint64(2250000000))
        
        #查询未花费记录
        #cursor = await db_connection.execute("SELECT * from coin_record WHERE coin_name=?", ("812f069fe739af997478857aefb04181afd91d47b565f132f5c84c23057db669",))
        cursor = await db_connection.execute("SELECT * from coin_record WHERE spent=0 and puzzle_hash in ("+AllPuzzleHashArrayText+")")
        rows = await cursor.fetchall()
        
        #r.delete("CHIA_DUST_ATTACK_COIN_USDED")
        print(len(rows))
        counter = 0
        counter1 = 0
        for row in rows:            
            coin = Coin(bytes32(bytes.fromhex(row[6])), bytes32(bytes.fromhex(row[5])), uint64.from_bytes(row[7]))
            CoinisUsed = r.hget("CHIA_DUST_ATTACK_COIN_USDED",coin.name());
            if CoinisUsed == None:
                coinList            = []
                CurrentCoinAmount   = 0
                CurrentCoinAmount   = uint64.from_bytes(row[7])
                coinList.append(coin)
                
                if(CurrentCoinAmount>=(SendToAmount+fee)):
                    print(f"coin.name(): {coin.name()} {CurrentCoinAmount}")
                    #coinList里面是一个数组,里面包含有的COIN对像. 这个函数可以传入多个COIN,可以实现多个输入,对应两个输出的结构.
                    generate_signed_transaction = self.generate_signed_transaction_multiple_coins(
                        SendToAmount,
                        SendToPuzzleHash,
                        coinList,
                        {},
                        fee,
                    )
                    print(str(generate_signed_transaction.name()))
                    #提交交易记录到区块链网络
                    push_res = await self.push_tx(generate_signed_transaction)
                    if  "success" in push_res and push_res['success'] == True:
                        r.hset("CHIA_DUST_ATTACK_COIN_USDED",coin.name(),1);
                        print(counter1)
                        print(push_res)
                        counter1 = counter1 +1
                    else:
                        counter = counter +1
                        print(counter)
                        print(push_res)
                    if counter >= 3:
                        break;
        
        await cursor.close()
        await db_connection.close()
        
        
        
        
        
        
    async def push_tx(self,generate_signed_transaction):
        try:
            config = load_config(DEFAULT_ROOT_PATH, "config.yaml")
            self_hostname = config["self_hostname"]
            rpc_port = config["full_node"]["rpc_port"]
            client_node = await FullNodeRpcClient.create(self_hostname, uint16(rpc_port), DEFAULT_ROOT_PATH, config)
            push_res = await client_node.push_tx(generate_signed_transaction)
            return push_res
        except Exception as e:
            push_res = {}
            push_res['success'] = "False"
            push_res['Exception'] = e
            return push_res
        finally:
            client_node.close()
            await client_node.await_closed()
        
            
    def get_next_address_index(self) -> uint32:
        self.next_address = uint32(self.next_address + 1)
        return self.next_address

    def get_private_key_for_puzzle_hash(self, puzzle_hash: bytes32) -> PrivateKey:
        if puzzle_hash in self.puzzle_pk_cache:
            child = self.puzzle_pk_cache[puzzle_hash]
            private = master_sk_to_wallet_sk(self.private_key, uint32(child))
            #  pubkey = private.get_g1()
            return private
        else:
            for child in range(0,50):
                pubkey = master_sk_to_wallet_sk(self.private_key, uint32(child)).get_g1()
                #print(type(puzzle_hash))
                #print(type(puzzle_for_pk(bytes(pubkey)).get_tree_hash()))
                #print(puzzle_hash)
                if puzzle_hash == puzzle_for_pk(bytes(pubkey)).get_tree_hash():
                    print('===================')
                    return master_sk_to_wallet_sk(self.private_key, uint32(child))
            '''        
            for child in range(0,50):
                pubkey = master_sk_to_wallet_sk_unhardened(self.private_key, uint32(child)).get_g1()
                #print(type(puzzle_hash))
                #print(type(puzzle_for_pk(bytes(pubkey)).get_tree_hash()))
                #print(puzzle_hash)
                if puzzle_hash == puzzle_for_pk(bytes(pubkey)).get_tree_hash():
                    print('===================')
                    return master_sk_to_wallet_sk_unhardened(self.private_key, uint32(child))
            '''
        raise ValueError(f"Do not have the keys for puzzle hash {puzzle_hash}")

    def puzzle_for_pk(self, pubkey: bytes) -> Program:
        return puzzle_for_pk(pubkey)

    def get_new_puzzle(self) -> bytes32:
        next_address_index: uint32 = self.get_next_address_index()
        pubkey = master_sk_to_wallet_sk(self.private_key, next_address_index).get_g1()
        self.pubkey_num_lookup[bytes(pubkey)] = next_address_index

        puzzle = puzzle_for_pk(bytes(pubkey))

        self.puzzle_pk_cache[puzzle.get_tree_hash()] = next_address_index
        return puzzle

    def get_new_puzzlehash(self) -> bytes32:
        puzzle = self.get_new_puzzle()
        return puzzle.get_tree_hash()

    def make_solution(self, condition_dic: Dict[ConditionOpcode, List[ConditionWithArgs]]) -> Program:
        ret = []
        #209732
        mystring = "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"
        mystring.encode('utf-8')
        Memos = []
        Memos.append(mystring)
        for con_list in condition_dic.values():
            for cvp in con_list:
                if cvp.opcode == ConditionOpcode.CREATE_COIN:
                    ret.append(make_create_coin_condition(cvp.vars[0], cvp.vars[1], Memos))
                if cvp.opcode == ConditionOpcode.CREATE_COIN_ANNOUNCEMENT:
                    ret.append(make_create_coin_announcement(cvp.vars[0]))
                if cvp.opcode == ConditionOpcode.CREATE_PUZZLE_ANNOUNCEMENT:
                    ret.append(make_create_puzzle_announcement(cvp.vars[0]))
                if cvp.opcode == ConditionOpcode.AGG_SIG_UNSAFE:
                    ret.append(make_assert_aggsig_condition(cvp.vars[0]))
                if cvp.opcode == ConditionOpcode.ASSERT_COIN_ANNOUNCEMENT:
                    ret.append(make_assert_coin_announcement(cvp.vars[0]))
                if cvp.opcode == ConditionOpcode.ASSERT_PUZZLE_ANNOUNCEMENT:
                    ret.append(make_assert_puzzle_announcement(cvp.vars[0]))
                if cvp.opcode == ConditionOpcode.ASSERT_SECONDS_ABSOLUTE:
                    ret.append(make_assert_absolute_seconds_exceeds_condition(cvp.vars[0]))
                if cvp.opcode == ConditionOpcode.ASSERT_SECONDS_RELATIVE:
                    ret.append(make_assert_relative_seconds_exceeds_condition(cvp.vars[0]))
                if cvp.opcode == ConditionOpcode.ASSERT_MY_COIN_ID:
                    ret.append(make_assert_my_coin_id_condition(cvp.vars[0]))
                if cvp.opcode == ConditionOpcode.ASSERT_HEIGHT_ABSOLUTE:
                    ret.append(make_assert_absolute_height_exceeds_condition(cvp.vars[0]))
                if cvp.opcode == ConditionOpcode.ASSERT_HEIGHT_RELATIVE:
                    ret.append(make_assert_relative_height_exceeds_condition(cvp.vars[0]))
                if cvp.opcode == ConditionOpcode.RESERVE_FEE:
                    ret.append(make_reserve_fee_condition(cvp.vars[0]))
                if cvp.opcode == ConditionOpcode.ASSERT_MY_PARENT_ID:
                    ret.append(make_assert_my_parent_id(cvp.vars[0]))
                if cvp.opcode == ConditionOpcode.ASSERT_MY_PUZZLEHASH:
                    ret.append(make_assert_my_puzzlehash(cvp.vars[0]))
                if cvp.opcode == ConditionOpcode.ASSERT_MY_AMOUNT:
                    ret.append(make_assert_my_amount(cvp.vars[0]))
        return solution_for_conditions(Program.to(ret))

    def generate_unsigned_transaction(
        self,
        amount: uint64,
        new_puzzle_hash: bytes32,
        coins: List[Coin],
        condition_dic: Dict[ConditionOpcode, List[ConditionWithArgs]],
        fee: int = 0,
        secret_key: Optional[PrivateKey] = None,
    ) -> List[CoinSpend]:
        spends = []
        
        spend_value = sum([c.amount for c in coins])

        if ConditionOpcode.CREATE_COIN not in condition_dic:
            condition_dic[ConditionOpcode.CREATE_COIN] = []
        if ConditionOpcode.CREATE_COIN_ANNOUNCEMENT not in condition_dic:
            condition_dic[ConditionOpcode.CREATE_COIN_ANNOUNCEMENT] = []

        output = ConditionWithArgs(ConditionOpcode.CREATE_COIN, [hexstr_to_bytes(new_puzzle_hash), int_to_bytes(amount)])
        condition_dic[output.opcode].append(output)
        amount_total = sum(int_from_bytes(cvp.vars[1]) for cvp in condition_dic[ConditionOpcode.CREATE_COIN])
        change = spend_value - amount_total - fee
        if change > 0:
            #change_puzzle_hash = self.get_new_puzzlehash()
            #print(type(change_puzzle_hash))
            #break;
            change_puzzle_hash = bytes32(bytes.fromhex("04cef8e607b69bea527f1de60b2ce9789352c94e2c36aa395d80d3bb99247bae"))
            #print(type(change_puzzle_hash))
            change_output = ConditionWithArgs(ConditionOpcode.CREATE_COIN, [change_puzzle_hash, int_to_bytes(change)])
            condition_dic[output.opcode].append(change_output)

        secondary_coins_cond_dic: Dict[ConditionOpcode, List[ConditionWithArgs]] = dict()
        secondary_coins_cond_dic[ConditionOpcode.ASSERT_COIN_ANNOUNCEMENT] = []
        
        for n, coin in enumerate(coins):
            puzzle_hash = coin.puzzle_hash
            #print(n);
            #print(coin);
            #print('----------------------')
            if secret_key is None:
                secret_key = self.get_private_key_for_puzzle_hash(puzzle_hash)
            pubkey = secret_key.get_g1()
            puzzle = puzzle_for_pk(bytes(pubkey))
            if n == 0:
                message_list = [c.name() for c in coins]
                for outputs in condition_dic[ConditionOpcode.CREATE_COIN]:
                    message_list.append(Coin(coin.name(), outputs.vars[0], int_from_bytes(outputs.vars[1])).name())
                message = std_hash(b"".join(message_list))
                condition_dic[ConditionOpcode.CREATE_COIN_ANNOUNCEMENT].append(
                    ConditionWithArgs(ConditionOpcode.CREATE_COIN_ANNOUNCEMENT, [message])
                )
                primary_announcement_hash = Announcement(coin.name(), message).name()
                secondary_coins_cond_dic[ConditionOpcode.ASSERT_COIN_ANNOUNCEMENT].append(
                    ConditionWithArgs(ConditionOpcode.ASSERT_COIN_ANNOUNCEMENT, [primary_announcement_hash])
                )
                main_solution = self.make_solution(condition_dic)
                spends.append(CoinSpend(coin, puzzle, main_solution))
            else:
                spends.append(CoinSpend(coin, puzzle, self.make_solution(secondary_coins_cond_dic)))
        return spends

    def sign_transaction(self, coin_spends: List[CoinSpend]) -> SpendBundle:
        signatures = []
        solution: Program
        puzzle: Program
        for coin_spend in coin_spends:  # type: ignore # noqa
            secret_key = self.get_private_key_for_puzzle_hash(coin_spend.coin.puzzle_hash)
            synthetic_secret_key = calculate_synthetic_secret_key(secret_key, DEFAULT_HIDDEN_PUZZLE_HASH)
            err, con, cost = conditions_for_solution(
                coin_spend.puzzle_reveal, coin_spend.solution, self.constants.MAX_BLOCK_COST_CLVM
            )
            if not con:
                raise ValueError(err)
            conditions_dict = conditions_by_opcode(con)

            for _, msg in pkm_pairs_for_conditions_dict(
                conditions_dict, bytes(coin_spend.coin.name()), self.constants.AGG_SIG_ME_ADDITIONAL_DATA
            ):
                signature = AugSchemeMPL.sign(synthetic_secret_key, msg)
                signatures.append(signature)
        aggsig = AugSchemeMPL.aggregate(signatures)
        spend_bundle = SpendBundle(coin_spends, aggsig)
        return spend_bundle
        
    def generate_signed_transaction_multiple_coins(
        self,
        amount: uint64,
        new_puzzle_hash: bytes32,
        coins: List[Coin],
        condition_dic: Dict[ConditionOpcode, List[ConditionWithArgs]] = None,
        fee: int = 0,
    ) -> SpendBundle:
        if condition_dic is None:
            condition_dic = {}
        transaction = self.generate_unsigned_transaction(amount, new_puzzle_hash, coins, condition_dic, fee)
        assert transaction is not None
        return self.sign_transaction(transaction)



if __name__ == "__main__":

    #config = load_config(Path(DEFAULT_ROOT_PATH), "config.yaml")
    #testnet_agg_sig_data = config["network_overrides"]["constants"]["testnet10"]["AGG_SIG_ME_ADDITIONAL_DATA"]
    #DEFAULT_CONSTANTS = DEFAULT_CONSTANTS.replace_str_to_bytes(**{"AGG_SIG_ME_ADDITIONAL_DATA": testnet_agg_sig_data})


    wt=WalletTool(DEFAULT_CONSTANTS)
    asyncio.run(wt.push_transaction())
    
