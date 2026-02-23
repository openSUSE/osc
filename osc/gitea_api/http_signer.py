import datetime
import os
import base64
import hashlib
import sys

class HttpSigner:
    def __init__(self, login_obj):
        self.login_obj = login_obj

    def _get_signer_from_file(self):
        """
        Returns a signing function and algorithm name using a local private key file.
        """
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import rsa, ed25519, padding
        from cryptography.hazmat.primitives import hashes

        key_path = self.login_obj.ssh_key
        
        if not os.path.exists(key_path):
            raise FileNotFoundError(f"SSH private key not found at: {key_path}")

        with open(key_path, "rb") as key_file:
            private_key = serialization.load_ssh_private_key(key_file.read(), password=None)

        algorithm_name = ""
        if isinstance(private_key, ed25519.Ed25519PrivateKey):
            algorithm_name = "ed25519"
            
            def sign_func(data_bytes):
                return private_key.sign(data_bytes)
                
        elif isinstance(private_key, rsa.RSAPrivateKey):
            algorithm_name = "rsa-sha512"
            
            def sign_func(data_bytes):
                return private_key.sign(
                    data_bytes,
                    padding.PKCS1v15(),
                    hashes.SHA512()
                )
        else:
            raise ValueError(f"Unsupported key type: {type(private_key)}")

        return sign_func, algorithm_name

    def _get_signer_from_agent(self):
        """
        Returns a signing function and algorithm name using the SSH Agent.
        Requires 'paramiko'.
        """
        try:
            import paramiko
        except ImportError:
            raise ImportError("The 'paramiko' library is required for SSH Agent support. Please run: pip install paramiko")

        agent = paramiko.agent.Agent()
        agent_keys = agent.get_keys()
        
        if not agent_keys:
            raise RuntimeError("No keys found in SSH Agent. Is it running and have you added keys (ssh-add)?")

        target_fingerprint = self.login_obj.ssh_key_agent_pub
        found_key = None
        
        # Remove "SHA256:" prefix if present for calculation/comparison
        target_fp_clean = target_fingerprint
        if target_fp_clean.startswith("SHA256:"):
            target_fp_clean = target_fp_clean[7:]

        for key in agent_keys:
            # Calculate SHA256 fingerprint of the key to match against configuration
            # Paramiko keys have .asbytes() which gives the public key blob
            key_blob = key.asbytes()
            fp_bytes = hashlib.sha256(key_blob).digest()
            # OpenSSH uses standard base64 without padding usually, but python's b64encode adds padding.
            # We need to strip standard padding '='
            fp_str = base64.b64encode(fp_bytes).decode('ascii').rstrip('=')
            
            if fp_str == target_fp_clean:
                found_key = key
                break
                
        if not found_key:
            print("Available keys in agent:")
            for key in agent_keys:
                key_blob = key.asbytes()
                fp_bytes = hashlib.sha256(key_blob).digest()
                fp_str = base64.b64encode(fp_bytes).decode('ascii').rstrip('=')
                print(f" - {key.get_name()} SHA256:{fp_str}")
            raise ValueError(f"Key with fingerprint {target_fingerprint} not found in SSH Agent.")

        #print(f"Using SSH Agent key: {found_key.get_name()}")

        # Determine algorithm name
        # Paramiko's get_name() usually returns 'ssh-rsa', 'ssh-ed25519', etc.
        algo_map = {
            "ssh-ed25519": "ed25519",
            "ssh-rsa": "rsa-sha512", # We assume we want sha512 for RSA
            "rsa-sha2-512": "rsa-sha512",
            "rsa-sha2-256": "rsa-sha256"
        }
        
        # Default to the key type, mapped or raw
        algorithm_name = algo_map.get(found_key.get_name(), found_key.get_name())
        
        def sign_func(data_bytes):
            # agent.sign_data returns a Message object or bytes containing the SSH signature blob
            # The SSH signature blob is: [4 byte len][algo name][4 byte len][signature]
            # We need to send the signature part.
            
            # Note: For RSA, we might need to specify flags to get SHA512.
            # Paramiko's sign_ssh_data doesn't easily expose flags in the high level AgentKey API
            # in older versions, but let's try just signing. 
            # Modern agents usually negotiate or we might just get what we get.
            
            # If it is RSA, we really want rsa-sha2-512.
            # But paramiko AgentKey.sign_ssh_data just calls the agent.
            
            # result is a paramiko.message.Message or bytes
            # It typically contains the entire blob: [string algo][string sig]
            # Use key.sign_ssh_data(data)
            
            sig_result = found_key.sign_ssh_data(data_bytes)
            
            # sig_result is usually a paramiko.Message object.
            if hasattr(sig_result, 'rewind'):
                sig_result.rewind()
                # The structure is: string(algo), string(signature_blob)
                sig_algo = sig_result.get_string()
                sig_blob = sig_result.get_string()
                return sig_blob
            else:
                # Maybe it returned bytes? Parse it manually
                # SSH string format: 4 bytes len, string data
                # We skip the algo name
                import struct
                if not isinstance(sig_result, bytes):
                    raise TypeError(f"Unexpected return type from sign_ssh_data: {type(sig_result)}")
                
                offset = 0
                algo_len = struct.unpack('>I', sig_result[offset:offset+4])[0]
                offset += 4 + algo_len
                
                sig_len = struct.unpack('>I', sig_result[offset:offset+4])[0]
                offset += 4
                sig_blob = sig_result[offset:offset+sig_len]
                return sig_blob

        return sign_func, algorithm_name
    
    def get_signed_header(self, method, path):
        """
        Sign the request data using the configured authentication method (SSH key or agent).
        Returns a tuple of (signature, algorithm_name).
        """
        if self.login_obj.ssh_key:
            sign_func, algorithm_name = self._get_signer_from_file()
        elif self.login_obj.ssh_agent:
            sign_func, algorithm_name = self._get_signer_from_agent()
        else:
            raise ValueError("No SSH authentication method configured for this login entry.")
        
        # Timestamps
        now = datetime.datetime.now(datetime.timezone.utc)
        created = int(now.timestamp())
        expires = int((now + datetime.timedelta(seconds=10)).timestamp())

        # (request-target): lowercase_method path
        if path.startswith("http"):
            from urllib.parse import urlparse

            parsed = urlparse(path)
            path = parsed.path
            if parsed.query:
                path += f"?{parsed.query}"

        request_target_value = f"{method.lower()} {path}"
        
        #print(f"Signing request target: {request_target_value}")
        
        signing_string = (
            f"(request-target): {request_target_value}\n"
            f"(created): {created}\n"
            f"(expires): {expires}"
        )
        
        try:
            signature_bytes = sign_func(signing_string.encode('utf-8'))
            signature_b64 = base64.b64encode(signature_bytes).decode('utf-8')
        except Exception as e:
            raise RuntimeError(f"Failed to sign data: {e}")

        headers_list = "(request-target) (created) (expires)"
        
        signature_header = (
            f'keyId="{self.login_obj.ssh_key_agent_pub}",'
            f'algorithm="{algorithm_name}",'
            f'headers="{headers_list}",'
            f'signature="{signature_b64}",'
            f'created={created},'
            f'expires={expires}'
        )

        headers = {
            'Signature': signature_header
        }
        
        return headers